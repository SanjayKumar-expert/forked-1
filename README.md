# hydroqc2mqtt

[![GitHub License](https://img.shields.io/github/license/SanjayKumar-expert/forked-1)](https://github.com/SanjayKumar-expert/forked-1/blob/main/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Issues](https://img.shields.io/github/issues/SanjayKumar-expert/forked-1)](https://github.com/SanjayKumar-expert/forked-1/issues)
[![GitHub Stars](https://img.shields.io/github/stars/SanjayKumar-expert/forked-1)](https://github.com/SanjayKumar-expert/forked-1/stargazers)
[![Discord](https://img.shields.io/discord/DISCORD_ID?label=Discord&logo=discord&logoColor=white)](https://discord.gg/2NrWKC7sfF)

> 🏡 **Smart Home Integration** | 🔌 **MQTT Publishing** | 📊 **Energy Monitoring** | 🇨🇦 **Hydro-Quebec**

**The full updated project documentation can be found at [https://hydroqc.ca](https://hydroqc.ca)**

## 🌟 Overview

This module extracts data from your **Hydro-Quebec account** using the [Hydro Quebec API Wrapper](https://gitlab.com/hydroqc/hydroqc) and publishes it to your **MQTT server**. Home-Assistant MQTT Discovery topics are automatically provided, enabling seamless sensor creation in **Home-Assistant**.

### ✨ Key Features

- 🔄 **Real-time Data Extraction** from Hydro-Quebec accounts
- 📡 **MQTT Integration** with automatic Home Assistant discovery
- 📈 **Historical Consumption Data** sent directly to Home-Assistant via WebSocket
- 🏠 **Energy Dashboard** compatible with Home-Assistant statistics
- 🐳 **Docker Support** for easy deployment
- ⚡ **Hourly Consumption Tracking** for detailed energy monitoring

## 🚀 Quick Start

### Using Docker
```bash
docker run -d \
  --name hydroqc2mqtt \
  -v /path/to/config.yaml:/app/config.yaml \
  your-image-name
```

### Manual Installation
```bash
pip install hydroqc2mqtt
hydroqc2mqtt --config config.yaml
```

## 📋 Requirements

- **Python 3.12+**
- Valid **Hydro-Quebec account**
- **MQTT Broker** (like Mosquitto)
- **Home Assistant** (optional, for full integration)

## 🤝 Community & Support

We have a discord server where you can discuss and find help with the project:

[![Join Discord](https://img.shields.io/badge/Join-Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/2NrWKC7sfF)

## 💖 Donations

We put a lot of heart and effort into this project. Any contribution is greatly appreciated!

[![Donate](https://img.shields.io/badge/Donate-Hydroqc-green?style=for-the-badge)](https://hydroqc.ca/en/donations)

## ⚠️ Disclaimer

### **Not an official Hydro-Quebec API**

This is a non-official way to extract your data from Hydro-Quebec. While it works now, it may break at any time if or when Hydro-Quebec changes their systems.

### **Special message to Hydro-Quebec's employees**

We would very much like to improve this module and its [API](https://gitlab.com/hydroqc). We tried to reach out to HQ but never were able to get in contact with anyone there interested in discussing this project. If you have feedback, complaints, or are interested in discussing this project, please reach out to us on our [development discord channel](https://discord.gg/NWnfdfRZ7T).

## 📄 License

This project is licensed under the **AGPL-3.0 License** - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <strong>Made with ❤️ for the Smart Home Community</strong>
</div>
