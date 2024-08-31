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
        echo "Cloning $NAME..."
        git clone "$GIT_URL" "$SENSOR_PATH"
    else
        echo "Updating $NAME..."
        git -C "$SENSOR_PATH" fetch origin
    fi

    # Checkout the specified version (branch, tag, or commit hash)

    # Determine if the version is a branch, tag, or commit hash
    if git -C "$SENSOR_PATH" rev-parse --verify "$GIT_VERSION" &>/dev/null; then
        # If it's a valid hash, checkout the commit directly
        echo "Checking out commit $GIT_VERSION for $NAME..."
        git -C "$SENSOR_PATH" checkout "$GIT_VERSION"
    elif git -C "$SENSOR_PATH" rev-parse --verify "origin/$GIT_VERSION" &>/dev/null; then
        # If it's a branch, checkout the branch
        echo "Checking out branch $GIT_VERSION for $NAME..."
        git -C "$SENSOR_PATH" checkout "$GIT_VERSION"
        git -C "$SENSOR_PATH" pull origin "$GIT_VERSION"
    elif git -C "$SENSOR_PATH" rev-parse --verify "refs/tags/$GIT_VERSION" &>/dev/null; then
        # If it's a tag, checkout the tag
        echo "Checking out tag $GIT_VERSION for $NAME..."
        git -C "$SENSOR_PATH" checkout "tags/$GIT_VERSION"
    else
        echo "Error: $GIT_VERSION is not a valid branch, tag, or commit hash for $NAME."
        continue
    fi

    # Launch the sensor in the background
    echo "Launching $NAME: $ENTRY_POINT --name $NAME --hash $HASH $ARGS"
    (cd "$SENSOR_PATH" && "../../$VENV_DIR/bin/python3" $ENTRY_POINT --name $NAME --hash $HASH $ARGS) &
done

# Wait for all background processes to finish
wait
