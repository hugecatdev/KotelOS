PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
case $TERM in xterm*) PS1='\[\033]0;\u@\h: \w\007\]'$PS1 ;; esac
export PS1
