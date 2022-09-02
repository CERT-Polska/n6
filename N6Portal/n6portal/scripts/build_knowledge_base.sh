#!/bin/bash

## This script helps with creating the template of the knowledge base
## structure. The destination of the knowledge base structure is
## taken from the parameter `knowledge_base.base_dir` taken from
## the `.ini` file given in the first parameter of this script.
##
## If the knowledge base structure does not exist in the given
## destination path, then it is created from the structure template
## given in `n6/etc/knowledge_base`. Otherwise script inform about
## existing knowledge base structure with asking about eventual
## deleting it before running.


set -e


## Variables and commands

# the path to the `.ini` file with `knowledge_base.base_dir` parameter
config_file_path=$1
# the path to the template of the knowledge base structure
knowledge_base_template_path="$PWD/etc/knowledge_base/"
cmd_cp="cp -rf"


## Helper functions

function get_knowledge_base_template_path() {
    if [[ -f $config_file_path ]]; then
        config_line=$(cat "$config_file_path" | grep knowledge_base.base_dir)
        # Remove everything from the beginning of the string until
        # the first occurrence of "=" and then trim leading and trailing
        # whitespaces
        local result=${config_line#*=}
        result=$(echo -e "$result" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        # Replace tilde with $HOME
        echo "${result/#\~/$HOME}"
    fi
}


## Main program

echo "----------------------------------------------------------------"
echo "           Creating initial knowledge base structure            "
echo "----------------------------------------------------------------"

knowledge_base_destination_path=$(get_knowledge_base_template_path)

if [[ -z $knowledge_base_destination_path ]]; then
    echo "The knowledge base template path not found in config file '$config_file_path'."
    echo "Please check if the first parameter of this script leads to apriopriate '*.ini' file."
    echo "----------------------------------------------------------------"
    exit 1
fi

if [[ -d  $knowledge_base_destination_path ]]; then
    echo "Knowledge base destination path '$knowledge_base_destination_path' already exists!"
    echo "Please remove it before using the script."
    echo "----------------------------------------------------------------"
    exit 1
fi

${cmd_cp} "${knowledge_base_template_path}" "${knowledge_base_destination_path}" || {
    echo "Cannot copy knowledge base template '${knowledge_base_template_path}' to '${knowledge_base_destination_path}'."
    exit 1
}

echo "Initial knowledge base structure has been created in a '$knowledge_base_destination_path'."
echo "----------------------------------------------------------------"
