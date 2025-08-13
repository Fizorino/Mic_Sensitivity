# Mic Sensitivity GUI

This project provides a graphical user interface (GUI) for interfacing with a UPV (Universal Precision Voltage) device. The application allows users to connect to the UPV, apply settings, and fetch measurement data, all through an intuitive interface.

## Project Structure

```
mic-sensitivity-gui
├── src
│   ├── main.py          # Entry point of the application
│   ├── gui
│   │   └── window.py    # Contains the MainWindow class for the GUI
│   ├── upv
│   │   └── upv_auto_config.py  # Existing code for UPV device interaction
│   └── utils
│       └── __init__.py  # Utility functions and classes
├── requirements.txt      # List of dependencies
└── README.md             # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd mic-sensitivity-gui
   ```

2. **Install dependencies:**
   It is recommended to use a virtual environment. You can create one using:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

   Then install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. **Run the application:**
   Execute the main script to launch the GUI:
   ```
   python src/main.py
   ```

2. **Connect to UPV:**
   Use the provided buttons in the GUI to connect to the UPV device.

3. **Apply Settings:**
   Configure the settings as needed and apply them through the interface.

4. **Fetch Data:**
   Initiate data fetching and view the results directly in the application.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.