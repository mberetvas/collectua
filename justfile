# Set a reliable shell for Windows users
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Default: list available recipes
default:
    @just --list

run-opcua-server:
    @echo "Running OPC UA server for testing..."
    @echo "This will start the OPC UA server on url opc.tcp://localhost:50000"
    @echo "You can use this server for testing collectua"
    @echo "To view the server logs, run: docker logs -f opcplc"
    @echo "To stop the server, run: docker stop opcplc"
    @echo "You can also use the just commands to view the logs and stop the server"
    @echo "just view-server-logs"
    @echo "just stop-server"

    docker run --rm -it -d -p 50000:50000 -p 8080:8080 --name opcplc mcr.microsoft.com/iotedge/opc-plc:latest --pn=50000 --autoaccept --sph --sn=5 --sr=10 --st=uint --fn=5 --fr=1 --ft=uint --gn=5 --dca --alm

view-server-logs:
    @echo "Viewing OPC UA server logs..."
    docker logs -f opcplc

stop-server:
    @echo "Stopping OPC UA server..."
    docker stop opcplc
collectua args='':
    @uv run collectua {{ args }}

test:
    uv run pytest