# Unofficial Speediance Workout Manager

A desktop web interface for managing Speediance Gym Monster workouts, viewing the exercise library, and generating AI-powered plans.

## What's New in v0.8

- **Unit Conversion Support**: Fully supports both Metric (kg) and Imperial (lbs) units. Switch your preference in the Settings menu, and the Workout Builder will automatically adjust limits and display values.
- **Support the Developer**: Added a "Buy Me a Coffee" link for those who wish to support the project's development.
- **UI Improvements**: Various layout tweaks and optimizations.

## Features

- **Exercise Library**: Browse and filter all available exercises with local caching for speed.
- **Workout Builder**: Create custom workouts with a drag-and-drop interface (or click-to-add).
- **AI Workout Generator (Experimental)**: Generate prompts for LLMs (ChatGPT/Claude) to create structured workout plans and import them directly via JSON.
- **Workout Manager**: View, edit, and delete custom workouts.
- **Offline Media**: Cache images and videos locally to reduce bandwidth and improve loading times.
- **E2E Testing**: Includes a test suite to verify workout creation and API integration.

## Installation & Usage

### Option A: Windows Executable (Recommended for most users)
1.  Download the latest `UnofficialSpeedianceWorkoutManager.exe` from the [Releases page](https://github.com/hbui3/UnofficialSpeedianceWorkoutManager/releases).
2.  Double-click the `.exe` file to run it.
    *   *Note: Windows Defender might warn you because this app is not signed. Click "More Info" -> "Run Anyway".*
3.  A control window will appear, and your default web browser will automatically open to the application.
4.  **Do not close the control window** while using the app. To stop the server, click "Stop Server & Exit" in the control window.

### Option B: Running from Source (For developers)
1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Copy `config.example.json` to `config.json`.
4.  Run the application:
    ```bash
    python app.py
    ```
5.  Open your browser at `http://localhost:5001`.

## Configuration

1.  Go to **Settings** and log in with your Speediance account credentials.
2.  **Unit System**: You can switch between Metric (KG) and Imperial (LBS) in the Settings page. This will adjust the Workout Builder limits and display units accordingly.

## Usage Guide

### 1. Authentication
Before you can manage workouts, you need to authenticate:
1. Navigate to the **Settings** page.
2. Enter your Speediance account email and password.
3. Click **Login**. Your session token will be saved locally to `config.json`.

### 2. Browsing Exercises
1. Click on **Library** in the navigation bar.
2. Use the search bar or muscle group filters to find exercises.
3. Click on any exercise to view details, videos, and instructions.

### 3. Creating a Custom Workout
1. Click on **Create Plan**.
2. **Add Exercises**: Click on exercises in the library sidebar (left) to add them to your plan (right).
3. **Configure Sets**:
   - Adjust sets, reps, weight, and rest times.
   - Select "Standard", "Chains", or "Eccentric" modes.
   - Choose presets (e.g., "Gain Muscle", "Strength") to auto-fill recommended ranges.
4. **Save**: Enter a name and click **Save**. The workout will sync to your Speediance device.

### 4. Experimental AI Features
Use the power of LLMs to design workouts:
1. Expand the **Experimental AI Features** section in the Workout Builder.
2. Click **Generate Prompt**.
3. Describe your goal (e.g., "45 min chest and triceps hypertrophy").
4. Click **Generate Full Prompt** and copy the result.
5. Paste this prompt into ChatGPT, Claude, or another LLM.
6. Copy the JSON response from the LLM.
7. Click **Import JSON** in the Speediance Desktop app and paste the code.
8. The workout will be automatically built with the correct exercises and settings.

### 5. Offline Mode
To speed up the interface:
1. Go to **Settings**.
2. Click **Download All Assets**.
3. This downloads all exercise media to `static/media_cache`.

## Testing

The project includes an End-to-End (E2E) test script to verify core functionality.

To run the tests:
```bash
python test_e2e_workouts.py
```
This script simulates a user logging in, creating a workout, and verifying the data structure.

## Known Issues & Limitations

### Regional Differences
- The API endpoints used are based on the global/US servers. Users in China or other specific regions might use different API endpoints which are not currently supported.

## Disclaimer

This is an unofficial tool and is not affiliated with Speediance. Use at your own risk.
