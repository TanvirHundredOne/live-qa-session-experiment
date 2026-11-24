SOURCE_DIR="video_datasets"
DEST_DIR="${SOURCE_DIR}_compressed"

find "$SOURCE_DIR" -type f | while IFS= read -r file; do
    rel_path="${file#$SOURCE_DIR/}"
    dest_file="$DEST_DIR/$rel_path"
    mkdir -p "$(dirname "$dest_file")"

    lower_file=$(printf '%s' "$file" | tr '[:upper:]' '[:lower:]')
    if [[ "$lower_file" == *.mp4 ]]; then
        ffmpeg -nostdin -i "$file" -c:v libx265 -crf 22 -preset medium -tag:v hvc1 -c:a copy "$dest_file"
    else
        cp "$file" "$dest_file"
    fi
done
