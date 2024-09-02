# StarkShift

StarkShift is an arbitrage bot for the StarkNet ecosystem, designed to take
advantage of price differences between centralised and decentralised exchanges.

## Installation

There are two methods to install and run StarkShift:

### Method 1: Using Poetry

StarkShift uses the `starknet.py` library, which has some external dependencies.
Before proceeding with the installation, please refer to the [starknet.py
installation
guide](https://starknetpy.readthedocs.io/en/latest/installation.html) to ensure
all prerequisites are met.

1. Ensure you have Python 3.12+ and Poetry are installed
2. Clone the repository:
   ```
   git clone https://github.com/Oghma/StarkShift.git
   cd starkshift
   ```
3. Install project dependencies:
   ```
   poetry install
   ```
   For MACOS users, add the flags before the command:
   ```
   CFLAGS=-I`brew --prefix gmp`/include LDFLAGS=-L`brew --prefix gmp`/lib poetry install
   ```

### Method 2: Using Docker

1. Ensure you have Docker installed on your system.
2. Clone the repository:
   ```
   git clone https://github.com/Oghma/StarkShift.git
   cd starkshift
   ```
3. Build the Docker image:
   ```
   docker build -t starkshift .
   ```

## Configuration

Before running StarkShift, you need to configure it:

- Edit `config.yaml` with your specific settings:
   - Set your StarkNet node URL (`node_url`)
   - Configure your base and quote tokens
   - Set your exchange API keys (`api_key`, `secret_key`)
   - Configure your StarkNet account (`account_address`, `signer_key`)
   - Adjust trading parameters:
     - `max_amount_trade`: maximum amount the bot is allowed to trade
     - `min_amount_trade`: minimum amount the bot is allowed to trade
     - `spread_threshold`: Threshold spread must exceed to consider trade profitable

## Usage

### Running with Poetry

- Run the bot:
   ```
   poetry run python -m starkshift [path_to_config]
   ```

### Running with Docker

1. Run the Docker container, mounting your configuration file:
   ```
   docker run -v $(pwd)/config.yaml:/app/config.yaml starkshift
   ```

This command mounts your local `config.yaml` file into the Docker container,
ensuring that your configuration is used when running the bot.
