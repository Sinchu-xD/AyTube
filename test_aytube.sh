#!/bin/bash
# aytube — working features test
# Usage: bash test_aytube.sh [--proxy URL] [--cookies FILE]

set -e

PROXY=""
COOKIES=""
TEST_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
TEST_ID="dQw4w9WgXcQ"
SEARCH_QR="lofi hip hop"
DELAY=3

# Parse args
while [ $# -gt 0 ]; do
    case "$1" in
        --proxy) PROXY="-p $2"; shift 2 ;;
        --cookies) COOKIES="-c $2"; shift 2 ;;
        *) shift ;;
    esac
done

ARGS="$PROXY $COOKIES"
echo "========================================="
echo "  aytube — Working Features Test"
echo "========================================="
echo "Proxy: ${PROXY:-none}"
echo "Cookies: ${COOKIES:-none}"
echo "Delay: ${DELAY}s between tests"
echo ""

test() {
    echo "━━━ $1 ━━━"
    eval "$2"
    echo ""
    sleep $DELAY
}

# 1. Metadata
test "1. info (metadata)" \
    "python3 -m aytube info '$TEST_URL' $ARGS"

# 2. List formats
test "2. list (formats)" \
    "python3 -m aytube list '$TEST_URL' $ARGS"

# 3. Get stream URL (1080p)
test "3. get (stream URL)" \
    "python3 -m aytube get '$TEST_URL' -q 1080p $ARGS"

# 4. Audio only
test "4. get (audio only)" \
    "python3 -m aytube get '$TEST_URL' -a $ARGS"

# 5. JSON output
test "5. info (JSON)" \
    "python3 -m aytube info '$TEST_URL' -j $ARGS"

# 6. Search
test "6. search" \
    "python3 -m aytube search '$SEARCH_QR' $ARGS -N 5"

# 7. Subtitles
test "7. subs (subtitles)" \
    "python3 -m aytube subs '$TEST_URL' $ARGS"

# 8. Thumbnail
test "8. thumb (thumbnail)" \
    "python3 -m aytube thumb $TEST_ID $ARGS -o /tmp/aytube_test_thumb.jpg"

# 9. Chapters
test "9. chapters" \
    "python3 -m aytube chapters '$TEST_URL' $ARGS"

# 10. Download
test "10. download" \
    "python3 -m aytube download '$TEST_URL' -q best -o /tmp/aytube_test_dl.mp4 $ARGS" || true

# 11. Download audio only
test "11. download (audio)" \
    "python3 -m aytube download '$TEST_URL' -a -o /tmp/aytube_test_audio.m4a $ARGS" || true

# 12. Specific format (itag 251 = audio only 160kbps)
test "12. get (specific itag)" \
    "python3 -m aytube get '$TEST_URL' -f 251 $ARGS"

# 13. Help
test "13. help" \
    "python3 -m aytube --help"

echo "========================================="
echo "  All tests complete!"
echo "========================================="
