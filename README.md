# hydroqc2mqtt

This module extracts data from your Hydro-Quebec account using the [Hydro Quebec API Wrapper](https://gitlab.com/hydroqc/hydroqc) and will post it to your MQTT server. Home-Assistant MQTT Discovery topics are also provided, automating the creation of your sensors in Home-Assistant.

## Disclaimer

**Pre-release**

This a pre-release of a project that is being actively developped. Breaking changes may happen until we reach a first stable release. If you install a version that work well for you you may want to stick to it until things are fully stabilised.

**Not an official Hydro-Quebec API**

This is a non official way to extract your data from Hydro-Quebec, while it works now it may break at anytime if or when Hydro-Quebec change their systems.

## Installation steps

At the moment the only supported method of running the project is via shell, more options are coming soon (docker and hass addon)

### Shell

1. Clone the repo

   ```bash
   git clone https://gitlab.com/hydroqc/hydroqc2mqtt
   ```

2. Create a python virtual env and activate it

   ```bash
   python -m venv env
   . env/bin/activate
   ```

3. Install requirements and module

   ```bash
   pip install -r requirements.txt --no-cache-dir --force
   python setup.py develop
   ```

4. Copy and change the configuration to enable the sensors you want

   ```bash
   cp config.sample.yaml config.yaml
   ```

5. Copy and adapt run.sh to your MQTT configuration

   ```bash
   cp run.sample.sh run.sh
   chmod +x run.sh
   ```

6. Run it!

   ```bash
   ./run.sh
   ```

### Docker

A docker image will be created soon!

### HASS Addon

We are working with the author of [pyhydroquebec-hass-addons](https://github.com/arsenicks/pyhydroquebec-hass-addons) to migrate to the usage of the new hydroqc library.
