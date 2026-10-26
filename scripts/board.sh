#!/usr/bin/env bash
# Sets an issue's Status on the "Molecula roadmap" board (project 3), adding the issue first if
# it isn't on the board. Done is set by GitHub when the issue closes.
#   scripts/board.sh <issue#> <Backlog|Ready|In progress|In review>
set -euo pipefail

PROJECT_ID=PVT_kwHOBqTJc84BmlZm
STATUS_FIELD_ID=PVTSSF_lAHOBqTJc84BmlZmzhlNzbw

if [[ $# -ne 2 ]]; then
  echo "usage: scripts/board.sh <issue#> <Backlog|Ready|In progress|In review>" >&2
  exit 2
fi

issue=$1
case $2 in
  Backlog) option=ac21950a ;;
  Ready) option=4066b8bf ;;
  "In progress") option=017f3d0a ;;
  "In review") option=54a5bcff ;;
  *) echo "unknown status '$2': use Backlog, Ready, In progress or In review" >&2; exit 2 ;;
esac

item=$(gh api graphql -F number="$issue" -f query='
  query($number: Int!) {
    repository(owner: "DannyKuk", name: "molecula") {
      issue(number: $number) { projectItems(first: 20) { nodes { id project { id } } } }
    }
  }' --jq ".data.repository.issue.projectItems.nodes[] | select(.project.id == \"$PROJECT_ID\") | .id")

if [[ -z $item ]]; then
  item=$(gh project item-add 3 --owner DannyKuk \
    --url "https://github.com/DannyKuk/molecula/issues/$issue" --format json --jq .id)
fi

gh project item-edit --project-id "$PROJECT_ID" --id "$item" \
  --field-id "$STATUS_FIELD_ID" --single-select-option-id "$option" > /dev/null
echo "#$issue -> $2"
