# RailFlow - Agentic AI Platform

## Team: Synaptech
**Group:** ONL4_AIS3_S3

### Project Overview
EGY-RailFlow is a Mega Project designed to modernize Egypt's rail networks by introducing an autonomous and dynamic operating system.

### Core Objectives
* **Maximize network throughput** using intelligent scheduling.
* **Energy-Efficient Operation** through intelligent driving profiles.
* **Predictive Maintenance** to eliminate delays using Multi-Agent Systems.

### Team Members
1. Ahmed Saeed Abdullah Alshanwany (Team Leader)
2. Mohamed Mossad Shehta Abdalshafi
3. Shahd Mahmoud Mohamed Abdelrahman
4. Passant Mohamed Elsayed Saleh
5. Mariam Gamal Ahmed Kamal Askar

## Getting Started

Follow these steps to configure the PostgreSQL database, ingest the GTFS data from the zip archive, and run the FastAPI server along with the interactive Frontend Web Dashboard.

### Prerequisites

* Python 3.10+
* PostgreSQL database server
* A Groq API Key (Set up in the `.env` file)

### Installation & Database Setup

1. **Clone the repository** and navigate to the project root directory.
2. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables**:
   Create a `.env` file in the root directory and configure your PostgreSQL database credentials and Groq API key:
   ```env
   DB_HOST=127.0.0.1
   DB_PORT=5432
   DB_NAME=railflow
   DB_USER=postgres
   DB_PASSWORD=your_postgres_password
   GROQ_API_KEY=gsk_your_groq_api_key
   ```
4. **Import the GTFS Database Zip File**:
   * Create a folder named `data` in the root directory if it does not exist.
   * Place your GTFS database zip archive inside it and rename it to `data.zip` so its path is `data/data.zip`.
   * Run the import script to set up the `gtfs` schema, create the required 11 tables, and ingest all GTFS records:
     ```bash
     python import_gtfs.py
     ```
   * *Optional:* To reset all tables and perform a clean re-import, add the `--reset` flag:
     ```bash
     python import_gtfs.py --reset
     ```

### Running the Application

1. **Start the FastAPI Application Server**:
   ```bash
   python -m uvicorn backend.api.app:app --reload --port 8000
   ```
2. **Access the Application**:
   * **Frontend Web Interface & Dashboard**: Open your browser and navigate to [http://127.0.0.1:8000/](http://127.0.0.1:8000/). The page features a landing selection screen connecting you to both the **Passenger Assistant Chat** (User Mode) and the **Performance & Operations Dashboard** (Analyst Mode) with dynamic AI report generation.
   * **Interactive API Documentation (Swagger Docs)**: Navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to view and test all backend endpoints.
