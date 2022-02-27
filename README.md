# hydroqc2mqtt

This module extracts data from your Hydro-Quebec account using the [Hydro Quebec API Wrapper](https://gitlab.com/hydroqc/hydroqc) and will post it to your MQTT server. Home-Assistant MQTT Discovery topics are also provided, automating the creation of your sensors in Home-Assistant.

We started a discord server for the project where you can come to discuss and find help with the project [https://discord.gg/JaRfRJEByz](https://discord.gg/JaRfRJEByz)

## Disclaimer

### **Pre-release**

This a pre-release of a project that is being actively developped. Breaking changes may happen until we reach a first stable release. If you install a version that work well for you you may want to stick to it until things are fully stabilised.

### **Not an official Hydro-Quebec API**

This is a non official way to extract your data from Hydro-Quebec, while it works now it may break at anytime if or when Hydro-Quebec change their systems.

### **Special message to Hydro-Quebec's employees**

We would very much like to improve this module and it's [API](https://gitlab.com/hydroqc). We tried to reach out to HQ but never were able to get in contact with anyone there interested in discussing this project. If you have some feedback, complaints or are interested to discuss this project, please reach out to us on our [development discord channel](https://discord.gg/NWnfdfRZ7T).

## Installation steps

You can run the project via a HASSIO add-on, docker or via shell.

### Home-Assistant OS Add-on

We provide a home-assistant add-on [here](https://gitlab.com/hydroqc/hydroqc-hass-addons). This is the easiest way to get started.

### Docker

A docker image is now available to run hydroqc2mqtt. All configuration options need to be provided as environement variable. If your MQTT server does not require auth leave the MQTT_USERNAME and MQTT_PASSWORD values empty

```bash
docker run -d --rm --name hydroqc2mqtt \
-e MQTT_USERNAME='yourmqttusername' \
-e MQTT_PASSWORD='yourmqttpassword' \
-e MQTT_HOST='yourmqttserver' \
-e MQTT_PORT='1883' \
-e HQ2M_CONTRACTS_0_NAME='maison' \
-e HQ2M_CONTRACTS_0_USERNAME='HQUsername' \
-e HQ2M_CONTRACTS_0_PASSWORD='HQPassword' \
-e HQ2M_CONTRACTS_0_CUSTOMER='HQCustomerNo' \
-e HQ2M_CONTRACTS_0_ACCOUNT='HQAccountNo' \
-e HQ2M_CONTRACTS_0_CONTRACT='HQContractNo' \
registry.gitlab.com/hydroqc/hydroqc2mqtt:0.1.6
```

A list of all container version and their tags can be found here: [https://gitlab.com/hydroqc/hydroqc2mqtt/container_registry/2746219](https://gitlab.com/hydroqc/hydroqc2mqtt/container_registry/2746219). Try to avoid :latest or :main for now since they are not updating properly for now

The HQ2M values define your various contracts. They all have a numer "\_0_" that can be incremented if you have more than one contract.

```
# Name of the contract, will appear in Home Assistant and in the hydroqc topics.
HQ2M_CONTRACTS_0_NAME='maison' \

# Username for your HQ account
HQ2M_CONTRACTS_0_USERNAME='email@domain.tld'

# Your HQ account password
HQ2M_CONTRACTS_0_PASSWORD='Password'

# Customer number (Numéro de client) from your invoice.
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
   cd hydroqc2mqtt
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

5. Copy and adapt run.sh to your MQTT configuration. If your MQTT server does not require auth leave the MQTT_USERNAME and MQTT_PASSWORD values empty

   ```bash
   cp run.sample.sh run.sh
   chmod +x run.sh
   ```

6. Run it!

   ```bash
   ./run.sh
   ```

To update you have to re-rerun the steps above. A simple git pull is not sufficient.

## Sensor Description

Here is the description of some of the sensors we provide that we feel needed more details. You need to be careful when using the current state values since they get updated only when we refresh the data every 10 minutes. This is a behavior we want to improve [(issue #5)](https://gitlab.com/hydroqc/hydroqc2mqtt/-/issues/5). In the mean time you can use the start/end timestamp values for more precise automations. If you want more details about the logics of each period you can get more details here: [https://hydroqc.readthedocs.io/en/latest/wintercredit/lexicon.html](https://hydroqc.readthedocs.io/en/latest/wintercredit/lexicon.html)

|Default HA name and MQTT Topic | Values | Description |
|-|-|-|
|Current period state for winter credit / current wc period detail | anchor / normal / peak / anchor_critical / peak_critical | Current period name and state **Be aware this is updated every 10mins.**|
| wc next anchor start / end | timestamp | The timestamp for the next anchor period start and end. Can be used as triggers in home-assistant automations. Will always have a value |
| wc next peak start / end | timestamp | The timestamp for the next peak period start and end. Can be used as triggers in home-assistant automations. Will always have a value |
| wc next critical peak start / end | timestamp | The timestamp for the next critical peak period start and end. Can be used as triggers in home-assistant automations. Will be "Unavailable" when the next peak event is not critical |
| wc upcoming_critical_peak | true/false | Is there any critical peak in the future. Will be true as soon as we detect an announcement from Hydro and will return to false once there is no critical peak in the future.|
| wc critical peak in progress | true/false | Are we in a critical peak right now. **Be aware this is updated every 10mins.**|
| wc next anchor critical | true/false | Is the next anchor period linked to a critical peak. Will be true from the end of the last peak to the end of the next peak if the next peak is critical.|
| wc next peak critical | true/false | Is the next peak period critical. Will be true from the end of the last peak to the end of the next peak if the next peak is critical.|
| wc upcoming critical peak today/tomorrow morning/evening | true/false | Is there a critical peak planed in the specified period. Will remain true/false until the end of the day |
| wc yesterday morning/evening * | various | The values (credit, reference energy, erased energy, actual consumption) for the critical peaks that happened yesterday. Will be unavailable if there was no critical peak the day before. |
| wc critical | true/false | Will be true from the end of the last peak to the end of the next peak if the next peak is critical. Since it is a duplicate of "next peak critical" it may be removed in the future|
