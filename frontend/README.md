# 🖥️ Cerberus AI Frontend — Executive Control Room SPA

The **Cerberus AI Control Room** is an industrial-grade Single Page Application (SPA) built for real-time edge telemetry visualization, multi-camera surveillance, incident triage, and worker compliance management.

---

## 🛠️ Technology Stack

- **Core Framework:** React 19 + [TanStack Start](https://tanstack.com/start) / Router (File-based route splitting)
- **Styling Architecture:** Tailwind CSS v4 + Curated Industrial Dark Theme Design Tokens
- **Iconography:** Lucide React icons
- **Data Visualization:** Recharts (Dynamic compliance trend graphs, live latency histograms)
- **Data Transport:** Real-time WebSocket connection (`WS /ws`) + RESTful Fetch Client with live telemetry polling

---

## 📁 Application Architecture

```
frontend/
├── public/                 # Static assets, branding, and icons
├── src/
│   ├── components/        # Reusable UI components (AppShell, StatCards, ConfirmModal)
│   ├── hooks/             # Custom React hooks (Live telemetry polling, session helpers)
│   ├── lib/               # Telemetry types, data contexts, and formatting utilities
│   ├── routes/            # TanStack file-based routes
│   │   ├── __root.tsx     # Application shell layout wrapper
│   │   ├── index.tsx      # Executive Dashboard (/)
│   │   ├── live.tsx       # Multi-Camera Grid (/live)
│   │   ├── violations.tsx # Incident Verification & Triage (/violations)
│   │   ├── compliance.tsx # Worker Compliance & Proof Gallery (/compliance)
│   │   ├── zones.tsx      # Safety Zone PPE Rules (/zones)
│   │   ├── cameras.tsx    # Camera Stream Manager (/cameras)
│   │   ├── reports.tsx    # Compliance Audits (/reports)
│   │   └── model.tsx      # Hardware Telemetry & Capacity Intelligence (/model)
│   └── main.tsx           # React entrypoint
├── package.json           # Frontend dependencies
└── vite.config.ts         # Vite build and proxy configuration
```

---

## 🚀 Development & Production Build

### Install Dependencies
```bash
cd frontend
npm install
```

### Start Development Server
```bash
npm run dev
```

### Production Compilation
```bash
npm run build
```
Generates optimized client and server bundles in `.output/`.