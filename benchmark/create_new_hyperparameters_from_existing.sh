#!/bin/bash

INPUT_FILE=${1}
SOURCE_FILE=`basename ${INPUT_FILE}`
echo "Source File: ${SOURCE_FILE}"

ID=`uuid`
echo "New hyperparameters id: ${ID}"

NEW_FILE="hyperparameters-${ID}.json"
echo "New hyperparameters file: ${NEW_FILE}"

cat hyperparameters/${SOURCE_FILE} | sed '/"id": /c\  "id": "'${ID}'",' > hyperparameters/${NEW_FILE}

