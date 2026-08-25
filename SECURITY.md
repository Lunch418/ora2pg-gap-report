*English | [Русский](SECURITY.ru.md)*

# Security Policy

## Supported versions

Bug fixes and security patches only go out for the latest version published
on [PyPI](https://pypi.org/project/ora2pg-gap-report/). Older versions
aren't supported separately, update to the current one before reporting a
problem.

## What can actually be a vulnerability here

The main usage path (`ora2pg-gap-report`, without the `[oracle]` extra) is
plain Python with no external dependencies besides `rich`. It reads local
files (an already-exported Oracle DDL) and sends nothing over the network,
so the attack surface is narrow: mainly ReDoS risk in the detectors'
regular expressions (the input is an arbitrary text file anyone could send
you) and correctness of file-path parsing.

`ora2pg-gap-export` (requires `pip install "ora2pg-gap-report[oracle]"`) is
a separate command with a live connection to Oracle via `python-oracledb`.
The password is never accepted as a command-line argument (it would be
visible in `ps`/shell history), only via the `ORACLE_PASSWORD` environment
variable or an interactive prompt (`getpass`). If you find a way the
password or DSN can still leak (into a log, an exception, a child
process's arguments), that's the vulnerability worth reporting first.

## Reporting a vulnerability

**Don't open a public issue.** Use
[GitHub Security Advisories](https://github.com/Lunch418/ora2pg-gap-report/security/advisories/new)
for this repository, it's a private channel, nobody sees the contents
except the maintainers until you choose to disclose it yourself.

In your report, if possible include:

- a minimal reproducible example (a file/input that triggers the problem);
- the `ora2pg-gap-report` version (`ora2pg-gap-report --version`);
- how this differs from a regular bug, i.e. what actual threat it creates
  (not just "it throws an exception", but what you can actually get from
  it).

This is a one-person open-source project with no SLA, I'll try to respond
to a first report within a week, but there's no formal time commitment.
