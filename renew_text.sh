#!/bin/bash

# ignores empty results
shopt -s nullglob

SPOOLDIR="/var/spool/mlmmj/"
SKELPATH="/usr/local/share/mlmmj/text.skel/"

if [ -z $1 ] || [ -z $2 ]; then
  printf "Error, no arguments specified.\nUsage: %s LIST_NAME LANGUAGE\n" "$0"
  printf "Available languages are:\n"
  ls "$SKELPATH"
  exit 1
fi

# check if text directory exists
if [ ! -d "$SPOOLDIR/$1/text" ]; then
  printf "Text directory not found, are you sure the list %s exists?\n" "$1"
  exit 1
fi

# check if skel directory exists
if [ ! -d "$SKELPATH/$2" ]; then
  printf "Invalid language %s, available languages are:\n" "$2"
  ls "$SKELPATH"
  exit 1
fi

printf "Deleting old text files...\n"
rm -rf "$SPOOLDIR/$1/text"
printf "Copying new text files...\n"
cp -R "$SKELPATH/$2/." "$SPOOLDIR/$1/text"
printf "All done\n"
