#!/bin/bash -e

KSL_SCRIPT_DIR="$(dirname -- "$(readlink -f -- "$0")")"
KSL_INSTALL_DIR="${KSL_SCRIPT_DIR}/.."
KSL_PYTHON_VENV_DIR="$HOME/.klipper-status-led-env"

KLIPPER_PRINTER_DATA_DIR="$HOME/printer_data"

KSL_CONFIG_PATH="$KLIPPER_PRINTER_DATA_DIR/config"
KSL_CONFIG_FILE=""
KSL_SOCKET="$KLIPPER_PRINTER_DATA_DIR/comms/klippy.sock"
KSL_LOG_DIR="$KLIPPER_PRINTER_DATA_DIR/logs"

# TODO:
# Determine locations of
    # config file
    # socket path (default)
    # log file (default)
# Install dependencies
    # Pi5?
# Create python virtual environment
# Prepare and install service

verifyRequirements() {
    VERSION="3,7"

    printf "Checking Python version > $VERSION\n"
    python3 --version
    if ! python3 -c "import sys; exit(1) if sys.version_info <= ("$VERSION") else exit(0)"
        then
            printf "Not supported. Aborting installation."
            exit 1
    fi
}

readPathsFromUser() {
    printf "\nChecking whether the default config/socket/log paths exist\n"
    printf "Assuming printer data is in '$KLIPPER_PRINTER_DATA_DIR'\n"

    KEEP="n"
    while : ; do
        if [[ -d $KSL_CONFIG_PATH ]]
            then
                if [[ ! "$KEEP" =~ ^[nN]$ ]]
                    then
                        KSL_CONFIG_FILE="$KSL_CONFIG_PATH/status_led.cfg"
                        if [[ ! -e $KSL_CONFIG_FILE ]]
                            then
                                read -r -e -p "Create a skeleton config file? [Y/n]" CREATE_CONFIG_FILE
                                if [[ ! "$CREATE_CONFIG_FILE" =~ ^[nN]$ ]];
                                    then
                                        cp "$KSL_INSTALL_DIR/examples/skeleton_status_led.cfg" "$KSL_CONFIG_FILE"
                                        printf "Config file created.\n"
                                    else
                                        printf "The config file needs to be added manually.\n"
                                fi
                        fi
                        break
                fi
                printf "\nConfig directory is '$KSL_CONFIG_PATH'.\n"
                read -r -e -p "Keep this setting? [Y/n]" KEEP
            else
                printf "Directory does not exist.\n"
                KEEP="n"
        fi

        if [[ "$KEEP" =~ ^[nN]$ ]];
            then
                read -r -e -p "Set config directory (excluding filename): " KSL_CONFIG_PATH
        fi
    done

    KEEP="n"
    while : ; do
        if [[ -e $KSL_SOCKET ]]
            then
                if [[ ! "$KEEP" =~ ^[nN]$ ]]
                    then
                        break
                fi
                printf "\nSocket path is '$KSL_SOCKET'.\n"
                read -r -e -p "Keep this setting? [Y/n]" KEEP
            else
                printf "Path does not exist.\n"
                KEEP="n"
        fi

        if [[ "$KEEP" =~ ^[nN]$ ]];
            then
                read -r -e -p "Set socket path: " KSL_SOCKET
        fi
    done

    KEEP="n"
    while : ; do
        if [[ -d $KSL_LOG_DIR ]]
            then
                if [[ ! "$KEEP" =~ ^[nN]$ ]]
                    then
                        break
                fi
                printf "\nLog directory is '$KSL_LOG_DIR'.\n"
                read -r -e -p "Keep this setting? [Y/n]" KEEP
            else
                printf "Directory does not exist.\n"
                KEEP="n"
        fi

        if [[ "$KEEP" =~ ^[nN]$ ]];
            then
                read -r -e -p "Set log directory: " KSL_LOG_DIR
        fi
    done
}

installService() {
    printf "Installing service\n"

    SERVICE=$(cat "$KSL_SCRIPT_DIR"/klipper-status-led.service)
    SERVICE=${SERVICE//KSL_PYTHON_VENV_DIR/$KSL_PYTHON_VENV_DIR}
    SERVICE=${SERVICE//KSL_INSTALL_DIR/$KSL_INSTALL_DIR}
    SERVICE=${SERVICE//KSL_CONFIG_FILE/$KSL_CONFIG_FILE}
    SERVICE=${SERVICE//KSL_SOCKET/$KSL_SOCKET}
    SERVICE=${SERVICE//KSL_LOG_DIR/$KSL_LOG_DIR}

    echo "$SERVICE" | sudo tee /etc/systemd/system/klipper-status-led.service > /dev/null
    sudo systemctl unmask klipper-status-led.service
    sudo systemctl daemon-reload
    sudo systemctl enable klipper-status-led
}


if [[ "$EUID" == 0 ]]
    then
        printf "This script must not be run as root.\n"
        exit 1
fi

verifyRequirements
readPathsFromUser
installService