#!/bin/bash

# Script to compress lambda_function.py into lambda_function-test.zip
# Usage: ./compress_py_files.sh

# Set output filename
OUTPUT_FILENAME="lambda_function-test.zip"

# Check if lambda_function.py exists in the current directory
if [ ! -f "lambda_function.py" ]; then
    echo "Error: lambda_function.py not found in the current directory."
    exit 1
fi

# Create a temporary directory for the file
TEMP_DIR=$(mktemp -d)

# Copy the lambda_function.py to the temporary directory
echo "Compressing lambda_function.py to $OUTPUT_FILENAME"
cp "lambda_function.py" "$TEMP_DIR/"

# Change to the temporary directory
cd "$TEMP_DIR" || exit 1

# Create the ZIP archive
zip -r "$OUTPUT_FILENAME" lambda_function.py

# Move the ZIP back to the original directory
mv "$OUTPUT_FILENAME" "$OLDPWD/"

# Clean up temporary directory
cd "$OLDPWD" || exit 1
rm -rf "$TEMP_DIR"

echo "Successfully created $OUTPUT_FILENAME containing lambda_function.py"