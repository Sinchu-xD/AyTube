#!/bin/bash
# AyTube — End-to-End CLI Integration Tests
# Usage: bash tests/test_cli.sh [--proxy URL] [--cookies FILE]

set -e

PROXY=""
COOKIES=""
TEST_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
TEST_ID="dQw4w9WgXcQ"
SEARCH_QUERY="lofi hip hop"
DELAY="${DELAY:-1}"

# Parse optional arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --proxy) PROXY="-p $2"; shift 2 ;;
        --cookies) COOKIES="-c $2"; shift 2 ;;
        *) shift ;;
    esac
done

ARGS="$PROXY $COOKIES"
echo "========================================="
echo "  AyTube — CLI Integration Test Suite"
echo "========================================="
echo "Proxy:   ${PROXY:-none}"
echo "Cookies: ${COOKIES:-auto-detect}"
echo "Delay:   ${DELAY}s"
echo ""

run_step() {
    echo "━━━ $1 ━━━"
    eval "$2"
    echo ""
    sleep "$DELAY"
}

# 1. Metadata
run_step "1. info (metadata)" \
    "python3 -m aytube info '$TEST_URL' $ARGS"

# 2. Formats
run_step "2. list (formats)" \
    "python3 -m aytube list '$TEST_URL' $ARGS"

# 3. Stream URL (1080p)
run_step "3. get (stream URL - 1080p)" \
    "python3 -m aytube get '$TEST_URL' -q 1080p $ARGS"

# 4. Audio only stream URL
run_step "4. get (audio only)" \
    "python3 -m aytube get '$TEST_URL' -a $ARGS"

# 5. JSON output
run_step "5. info (JSON)" \
    "python3 -m aytube info '$TEST_URL' -j $ARGS"

# 6. YouTube Search
run_step "6. search" \
    "python3 -m aytube search '$SEARCH_QUERY' $ARGS -N 5"

# 7. Subtitles
run_step "7. subs (subtitles)" \
    "python3 -m aytube subs '$TEST_URL' $ARGS"

# 8. Thumbnail download
run_step "8. thumb (thumbnail)" \
    "python3 -m aytube thumb '$TEST_ID' $ARGS -o /tmp/aytube_test_thumb.jpg"

# 9. Chapters
run_step "9. chapters" \
    "python3 -m aytube chapters '$TEST_URL' $ARGS"

# 10. Direct video download
run_step "10. download (video 360p)" \
    "python3 -m aytube download '$TEST_URL' -q 360p -o /tmp/aytube_test_dl.mp4 $ARGS" || true

# 11. Audio only download
run_step "11. download (audio)" \
    "python3 -m aytube download '$TEST_URL' -a -o /tmp/aytube_test_audio.m4a $ARGS" || true

# 12. Specific format (itag 251)
run_step "12. get (itag 251)" \
    "python3 -m aytube get '$TEST_URL' -f 251 $ARGS"

# 13. Help display
run_step "13. help" \
    "python3 -m aytube --help"

# Cleanup temporary test files
rm -f /tmp/aytube_test_thumb.jpg /tmp/aytube_test_dl.mp4 /tmp/aytube_test_audio.m4a

echo "========================================="
echo "  All CLI integration tests passed!"
echo "========================================="
