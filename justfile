# Set a reliable shell for Windows users
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Default: list available recipes
default:
    @just --list