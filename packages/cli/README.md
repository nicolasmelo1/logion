# logion-cli

CLI for the Logion marketplace — discover, acquire, install, update,
and manage AI agent courses and capabilities.

## Install

```bash
pip install logion-cli
```

## Quick start

```bash
logion --help
logion courses get <COURSE_ID>
```

## Shell completion

`logion completion <shell>` prints a tab-completion script generated from
the live command tree (so it always covers every command and flag):

```bash
# bash — current session
eval "$(logion completion bash)"
# bash — persist
logion completion bash > ~/.local/share/bash-completion/completions/logion

# zsh — write to a directory on your $fpath
logion completion zsh > ~/.zfunc/_logion

# tcsh
logion completion tcsh > ~/.config/logion/completion.tcsh
```

## License

MIT