#!/bin/bash

echo "" >> bicycleinit.log
date >> bicycleinit.log
echo "${BASH_SOURCE[0]}" | tee -a bicycleinit.log

# Configuration file
CONFIG_FILE="config.json"

# Name of the virtual environment directory
VENV_DIR=".env"

# Create a directory for sensors
SENSOR_DIR="sensors"
mkdir -p "$SENSOR_DIR"

# Extract the hash from the .bicycledata file
HASH=$(jq -r '.hash' < .bicycledata)

# Iterate through each sensor entry in the config file
jq -c '.sensors[]' "$CONFIG_FILE" | while read sensor; do
    # Extract sensor details using jq
    NAME=$(echo "$sensor" | jq -r '.name')
    GIT_URL=$(echo "$sensor" | jq -r '.git_url')
    GIT_VERSION=$(echo "$sensor" | jq -r '.git_version')
    ENTRY_POINT=$(echo "$sensor" | jq -r '.entry_point')
    ARGS=$(echo "$sensor" | jq -r '.args | join(" ")')

    # Define the sensor directory
    SENSOR_PATH="$SENSOR_DIR/$NAME"

    # Clone the repository if it doesn't exist, otherwise pull the latest version
    if [ ! -d "$SENSOR_PATH" ]; then
        echo "Cloning $NAME..." | tee -a bicycleinit.log
        if ! git clone "$GIT_URL" "$SENSOR_PATH"; then
            echo "Failed to clone $NAME." | tee -a bicycleinit.log
            continue
        fi
    else
        echo "Updating $NAME..." | tee -a bicycleinit.log
        git -C "$SENSOR_PATH" fetch origin
    fi

    # Checkout the specified version (branch, tag, or commit hash)
    if git -C "$SENSOR_PATH" rev-parse --verify "$GIT_VERSION" &>/dev/null; then
        echo "Checking out commit $GIT_VERSION for $NAME..." | tee -a bicycleinit.log
        if ! git -C "$SENSOR_PATH" checkout "$GIT_VERSION"; then
            echo "Error: Failed to checkout commit $GIT_VERSION for $NAME." | tee -a bicycleinit.log
            continue
        fi
    elif git -C "$SENSOR_PATH" rev-parse --verify "origin/$GIT_VERSION" &>/dev/null; then
        echo "Checking out branch $GIT_VERSION for $NAME..." | tee -a bicycleinit.log
        if ! git -C "$SENSOR_PATH" checkout "origin/$GIT_VERSION"; then
            echo "Error: Failed to checkout branch $GIT_VERSION for $NAME." | tee -a bicycleinit.log
            continue
        fi
        if ! git -C "$SENSOR_PATH" pull origin "$GIT_VERSION"; then
            echo "Error: Failed to pull latest changes for branch $GIT_VERSION for $NAME." | tee -a bicycleinit.log
            continue
        fi
    elif git -C "$SENSOR_PATH" rev-parse --verify "refs/tags/$GIT_VERSION" &>/dev/null; then
        echo "Checking out tag $GIT_VERSION for $NAME..." | tee -a bicycleinit.log
        if ! git -C "$SENSOR_PATH" checkout "refs/tags/$GIT_VERSION"; then
            echo "Error: Failed to checkout tag $GIT_VERSION for $NAME." | tee -a bicycleinit.log
            continue
        fi
    else
        echo "Error: $GIT_VERSION is not a valid branch, tag, or commit hash for $NAME." | tee -a bicycleinit.log
        continue
    fi

    if [ -f "$SENSOR_PATH/requirements.txt" ]; then
        "$VENV_DIR/bin/pip3" install -q -r "$SENSOR_PATH/requirements.txt" | tee -a bicycleinit.log
        if [ $? -ne 0 ]; then
            echo "Failed to install requirements for $NAME." | tee -a bicycleinit.log
            continue
        fi
    fi

    # Launch the sensor in the background
    echo "Launching $NAME: $ENTRY_POINT --name $NAME --hash $HASH $ARGS" | tee -a bicycleinit.log
    (cd "$SENSOR_PATH" && "../../$VENV_DIR/bin/python3" $ENTRY_POINT --name $NAME --hash $HASH $ARGS) &
done

# Wait for all background processes to finish
wait
