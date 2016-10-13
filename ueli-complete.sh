_ueli_completion() {
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _UELI_COMPLETE=complete $1 ) )
    return 0
}

complete -F _ueli_completion -o default ueli;
