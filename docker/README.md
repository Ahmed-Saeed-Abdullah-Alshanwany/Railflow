# 🐋 PostgreSQL Docker Setup Guide

This guide provides step-by-step instructions on how to set up, configure, and spin up a **PostgreSQL** database container using **Docker**, and connect to it using **DBeaver**.

---

## 📋 Prerequisites

Before you start, ensure you have the following software installed on your machine:
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Must be running)
* [DBeaver Community Edition](https://dbeaver.io/download/) (Universal database management tool)

---

## ⚙️ 1. Environment Configuration

To keep credentials secure, they are excluded from version control via `.gitignore`. You must create a `.env` file from the provided `.env.example` template.

Open your terminal in the `docker` directory and run the appropriate command for your shell:

### 💻 Command Line Instructions:

* **Using Git Bash / Linux / macOS:**
  ```bash
  cp .env.example .env
  ```

* **Using Windows Command Prompt (cmd):**
  ```cmd
  copy .env.example .env
  ```

* **Using Windows PowerShell:**
  ```powershell
  Copy-Item .env.example .env
  ```

> [!TIP]
> Open the newly created `.env` file to customize any database configurations such as `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, or `POSTGRES_PORT`.
> If you have another PostgreSQL instance running on your host machine (default port `5432` is busy), you can change `POSTGRES_PORT` to `5435` or any other free port.

---

## 🚀 2. Spin Up the Docker Container

Once your `.env` file is ready, run the following commands to download and spin up the database container:

```bash
cd docker
docker compose up -d
```

* `-d`: Runs the container in the background (Detached Mode).

---

## 🛠️ 3. Default Connection Credentials

The database container is pre-configured with the following default values loaded from the `.env` file:

| Property | Default Value | Description |
| :--- | :--- | :--- |
| **Host** | `localhost` | Local database server address |
| **Port** | `5435` | Publicly exposed database port (avoiding `5432` conflicts) |
| **Database Name** | `railflow_db` | Initial target database created |
| **Username** | `postgres` | Administrative user |
| **Password** | `railflow_secure_password_2026` | Secure access password |

---

## 🔌 4. Connecting to the Database via DBeaver

Follow these simple steps to connect to your running PostgreSQL instance using **DBeaver**:

### Step 1: Create a New Database Connection
1. Launch **DBeaver**.
2. Click on **Database** in the top menu bar, then select **New Database Connection** (or click the green **`+` Plug** icon in the toolbar).
3. Search or choose **PostgreSQL** from the database list and click **Next**.

### Step 2: Configure Connection Settings
In the **Connection Settings** window, fill in the fields exactly as defined in the `.env` file:
* **Host**: `localhost`
* **Port**: `5435` (or whatever `POSTGRES_PORT` is set to in your `.env`)
* **Database**: `railflow_db`
* **Username**: `postgres`
* **Password**: `railflow_secure_password_2026`

> [!WARNING]
> Ensure there are no leading or trailing blank spaces in any of the fields (especially the password field) when pasting the details.

### Step 3: Test and Finalize the Connection
1. In the bottom-left corner of the wizard window, click the **Test Connection** button.
2. If prompted to download the PostgreSQL database drivers, click **Download** to proceed.
3. Upon a successful connection, you should see a **Connected** dialog showing details of the active PostgreSQL instance.
4. Click **OK**, then click **Finish** to save your new connection.
5. Your database will now appear in the DBeaver Database Navigator sidebar!

---

## 🛑 5. Stopping the Database Container

To stop the PostgreSQL database container and release system resources when you are done working, run the following command from the `docker` directory:

```bash
docker compose down
```

> [!IMPORTANT]
> Stopping the container using `docker compose down` will **not** lose your database schemas, tables, or records. All data is persistently saved inside a local Docker volume named `postgres_data`.
