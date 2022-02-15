# hydroqc2mqtt

This module extracts data from your Hydro-Quebec account using the [Hydro Quebec API Wrapper](https://gitlab.com/hydroqc/hydroqc) and will post it to your MQTT server. Home-Assistant MQTT Discovery topics are also provided, automating the creation of your sensors in Home-Assistant.

We started a discord server for the project where you can come to discuss and find help with the project [https://discord.gg/JaRfRJEByz](https://discord.gg/JaRfRJEByz)

## Disclaimer

### **Pre-release**

This a pre-release of a project that is being actively developped. Breaking changes may happen until we reach a first stable release. If you install a version that work well for you you may want to stick to it until things are fully stabilised.

### **Not an official Hydro-Quebec API**

This is a non official way to extract your data from Hydro-Quebec, while it works now it may break at anytime if or when Hydro-Quebec change their systems.

## Installation steps

You can run the project via docker or via shell.

### Docker

A docker image is now available to run hydroqc2mqtt. All configuration options need to be provided as environement variable.

```bash
docker run -d --rm --name hydroqc2mqtt \
-e MQTT_USERNAME='yourmqttusername' \ # Leave empty if no auth is needed
-e MQTT_PASSWORD='yourmqttpassword' \ # Leave empty if no auth is needed
-e MQTT_HOST='yourmqttserver' \
-e MQTT_PORT='1883' \
-e HQ2M_CONTRACTS_0_NAME='maison' \
-e HQ2M_CONTRACTS_0_USERNAME='HQUsername' \
-e HQ2M_CONTRACTS_0_PASSWORD='HQPassword' \
-e HQ2M_CONTRACTS_0_CUSTOMER='HQCustomerNo' \
-e HQ2M_CONTRACTS_0_ACCOUNT='HQAccountNo' \
-e HQ2M_CONTRACTS_0_CONTRACT='HQContractNo' \
registry.gitlab.com/hydroqc/hydroqc2mqtt:main  ## You can also specify a version that work well for you here (registry.gitlab.com/hydroqc/hydroqc2mqtt:0.1.1)
```


The HQ2M values define your various contracts. They all have a numer "\_0_" that can be incremented if you have more than one contract.


```
# Name of the contract, will appear in Home Assistant and in the hydroqc topics.
HQ2M_CONTRACTS_0_NAME='maison' \

# Username for your HQ account
HQ2M_CONTRACTS_0_USERNAME='email@domain.tld'

# Your HQ account password
HQ2M_CONTRACTS_0_PASSWORD='Password'

# Customer number (Numéro de facture) from your invoice.
# 10 digits, you may need to add a leading 0 to the value!!!
# Ex: '987 654 321' will be '0987654321'
HQ2M_CONTRACTS_0_CUSTOMER='0987654321'

# Account Number (Numéro de compte) from your invoice
HQ2M_CONTRACTS_0_ACCOUNT='654321987654'

# Contract Number (Numéro de contrat) from your invoice
# 10 digits, you may need to add a leading 0 to the value!!!
# Ex: '123 456 789' will be '0123456789'
HQ2M_CONTRACTS_0_CONTRACT='0123456789'

## 2nd contract example
HQ2M_CONTRACTS_1_NAME='chalet'
HQ2M_CONTRACTS_1_USERNAME='email@domain.tld'
HQ2M_CONTRACTS_1_PASSWORD='Password'
HQ2M_CONTRACTS_1_CUSTOMER='0987654321'
HQ2M_CONTRACTS_1_ACCOUNT='654321987654'
HQ2M_CONTRACTS_1_CONTRACT='0133446729'
```

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

### HASS Addon

We are working with the author of [pyhydroquebec-hass-addons](https://github.com/arsenicks/pyhydroquebec-hass-addons) to migrate to the usage of the new hydroqc library.
