# 🚀 LineUp System (Smart Virtual Queue Management System)
**ប្រព័ន្ធគ្រប់គ្រងជួរឆ្លាតវៃតាមប្រព័ន្ធឌីជីថល (Virtual Queue System)**

---

## 🌟 ១. ទិដ្ឋភាពទូទៅនៃគម្រោង (Project Overview)
**LineUp System** គឺជាប្រព័ន្ធគ្រប់គ្រងជួរឌីជីថលបែបទំនើប (Smart Virtual Queue) ដែលជួយដោះស្រាយបញ្ហាការកកស្ទះ និងការឈរតម្រង់ជួររង់ចាំយូរនៅតាម **គ្លីនិក មន្ទីរពេទ្យ ធនាគារ ហាង និងមណ្ឌលសេវាកម្ម**។

អតិថិជនគ្រាន់តែយកទូរស័ព្ទដៃស្កេន **QR Code** ដើម្បីទទួលបានលេខសំបុត្រឌីជីថល (Digital Ticket) រួចអាចដើរលេង ឬអង្គុយរង់ចាំដោយសេរី។ ប្រព័ន្ធនឹងធ្វើការគណនា **ចំនួនមនុស្សនៅខាងមុខ**, **ម៉ោងរង់ចាំប៉ាន់ស្មាន (Smart ETA)** និង **បន្លឺសំឡេងដាស់តឿន (Notification & Vibration)** ពេលជិតដល់វេន។

---

## 🏗️ ២. ស្ថាបត្យកម្មប្រព័ន្ធ (System Architecture)

ប្រព័ន្ធត្រូវបានរៀបចំឡើងជា ៤ ផ្ទាំង Interface សំខាន់ៗ៖

### 📱 ១. Customer Mobile Web App (`/`)
* **ស្កេន QR Code យកលេខភ្លាមៗ**: មិនបាច់ដំឡើង App (Zero-Install Web App)។
* **Live Queue Status**: បង្ហាញស្ថានភាពផ្ទាល់តាមរយៈ **WebSockets** (លេខបច្ចុប្បន្ន, ចំនួនអ្នកនៅខាងមុខ, ម៉ោងប៉ាន់ស្មាន ETA)។
* **No-Show Protection & Smart Alert**: ពេលនៅសល់ ២ នាក់ទៀត ឬដល់វេន ប្រព័ន្ធនឹងលោត Banner ដាស់តឿន, បន្លឺសំឡេង និងញ័រទូរស័ព្ទ (Vibration)។
* **Telegram Notification**: ជម្រើសផ្ញើសារដាស់តឿនចូល Telegram របស់អតិថិជន។

### 💻 ២. Staff / Admin Dashboard (`/staff`)
* **ការគ្រប់គ្រងបញ្ជរ**: ជ្រើសរើសបញ្ជរបម្រើសេវា (Counter 1 ដល់ Counter 6) និងប្រភេទសេវាកម្ម។
* **ប៊ូតុងបញ្ជា**: 
  - **Call Next (ហៅលេខបន្ទាប់)**: ហៅអតិថិជនដំបូងគេដែលកំពុងរង់ចាំ។
  - **Recall (ហៅម្តងទៀត)**: បន្លឺសំឡេង Ding-Dong និង Voice Announcement ម្តងទៀត។
  - **Serve (ចាប់ផ្តើមបម្រើ)**: កត់ត្រាម៉ោងចាប់ផ្តើមផ្តល់សេវា។
  - **Complete (បញ្ចប់សេវា)**: បញ្ចប់សេវា និងកត់ត្រារយៈពេលបម្រើ។
  - **Mark No-Show (ខកខានវេន)**: ដាក់ status ជា NO_SHOW ប្រសិនបើអតិថិជនមិនមកបង្ហាញខ្លួន។
* **Auto No-Show Timer (៣ នាទី)**: មាន Timer រាប់ថយក្រោយស្វ័យប្រវត្តិនៅលើផ្ទាំង Staff។
* **ស្ថិតិប្រចាំថ្ងៃ (Daily Analytics)**: ចំនួនភ្ញៀវសរុប, កំពុងរង់ចាំ, កំពុងបម្រើ, បានបញ្ចប់, ខកខានវេន, រយៈពេលរង់ចាំជាមធ្យម (Avg Wait Time), និងរយៈពេលបម្រើសេវាជាមធ្យម (Avg Service Time)។
* **ចេញសំបុត្រផ្ទាល់ (Walk-In Ticket)**: សម្រាប់ភ្ញៀវដែលមិនមានទូរស័ព្ទ។

### 📺 ៣. Public TV Display Board (`/tv`)
* **អេក្រង់ទំហំធំសម្រាប់ព្យួរក្នុងហាង**: រចនាឡើងយ៉ាងស្រស់ស្អាត ងាយមើលពីចម្ងាយ (គាំទ្រ Fullscreen Mode)។
* **Hero Spotlight Box**: បង្ហាញលេខសំបុត្រដែលកំពុងហៅយ៉ាងច្បាស់ (ឧ. `Ticket A-001 -> Counter 1`)។
* **All Counter Matrix (1-6)**: បង្ហាញស្ថានភាពបញ្ជរនីមួយៗថាតើកំពុងបម្រើលេខណា ឬទំនេរ។
* **Next in Line Ticker**: បង្ហាញលេខសំបុត្រដែលត្រូវដល់វេនបន្ទាប់។
* **Audio Chime & Multilingual TTS**:
  - បន្លឺសំឡេង **Airport/Bank Ding-Dong Chime** ដោយប្រើ **Web Audio API** (សំឡេងពិរោះ មិនបាច់ទាញយក file mp3 ពីក្រៅ)។
  - អានលេខសំបុត្រ និងបញ្ជរដោយស្វ័យប្រវត្តិតាមរយៈ **Web Speech API** ("Ticket A 0 0 1, please proceed to counter 1")។

### 🖨️ ៤. QR Code Kiosk Display (`/kiosk`)
* បង្ហាញ QR Code ធំច្បាស់សម្រាប់ដាក់នៅមាត់ទ្វារ ឬច្រកចូលហាង។
* បង្ហាញ IP Address ក្នុងបណ្តាញ Wi-Fi ដោយស្វ័យប្រវត្តិ (`http://192.168.x.x:8000/`)។
* មាន Touch Button សម្រាប់ចុចយកសំបុត្រភ្លាមៗនៅលើអេក្រង់ Kiosk ផងដែរ។

---

## 🛠️ ៣. បច្ចេកវិទ្យាប្រើប្រាស់ (Tech Stack)

| ផ្នែក | បច្ចេកវិទ្យា | ការពណ៌នា |
| :--- | :--- | :--- |
| **Backend** | Python (FastAPI) | លឿន, Async/Await, គាំទ្រ WebSockets និង Swagger Docs ដោយស្វ័យប្រវត្តិ |
| **Database** | SQLite + SQLAlchemy | ងាយស្រួល run demo លើ Laptop មិនបាច់ setup Database Server ស្មុគស្មាញ |
| **Real-time** | WebSockets (`ws://`) | Update ទិន្នន័យលើអេក្រង់ TV, Staff, និង Customer ភ្លាមៗដោយមិនបាច់ Refresh |
| **Audio & Speech** | Web Audio API + Web Speech API | បង្កើតសំឡេង Ding-Dong Chime និង Text-to-Speech (TTS) អានលេខសំបុត្រ |
| **QR Code** | Python `qrcode` + `Pillow` | បង្កើតរូបភាព QR Code ឌីជីថលតាម LAN IP ដោយស្វ័យប្រវត្តិ |
| **Frontend** | HTML5 + Tailwind CSS + Vanilla JS | Responsive UI ស្រាល លឿន គាំទ្រ Dark Mode |

---

## 👥 ៤. ការកំណត់សិទ្ធិប្រើប្រាស់តាម Role (Role-Based Access Control - RBAC)

ប្រព័ន្ធបានកំណត់សិទ្ធិយ៉ាងតឹងរ៉ឹង និងច្បាស់លាស់សម្រាប់ User នីមួយៗ៖

| Role (តួនាទី) | សិទ្ធិទទួលបាន (Permissions) | កម្រិតការពារ (Protection) |
| :--- | :--- | :--- |
| **អតិថិជន (Customer)** | • ចូលមើលទំព័រ `/` ដើម្បីយកលេខសំបុត្រឌីជីថល<br>• មើល Live Status, ចំនួនអ្នកនៅមុខ, ម៉ោងរង់ចាំ ETA<br>• ស្កេន QR Code នៅ Kiosk (`/kiosk`) ឬមើល TV Board (`/tv`)<br>• បោះបង់សំបុត្ររបស់ខ្លួន | **គ្មានសិទ្ធិ** ចូល Dashboard បុគ្គលិក ឬហៅលេខឡើយ (ប្រសិនបើព្យាយាមចូល `/staff` នឹងត្រូវ Redirect ទៅកាន់ទំព័រ `/login` ដោយស្វ័យប្រវត្តិ) |
| **បុគ្គលិក (Staff)** | • ចូល Dashboard បុគ្គលិក (`/staff`) តាមរយៈគណនី និងលេខសម្ងាត់<br>• ហៅលេខបន្ទាប់ (Call Next), ហៅម្តងទៀត (Recall), ចាប់ផ្តើមបម្រើ (Serve), បញ្ចប់ (Complete)<br>• ដាក់សញ្ញាខកខានវេន (Mark No-Show)<br>• ចេញសំបុត្រ Walk-In ជូនភ្ញៀវចាស់ជរា ឬអ្នកគ្មានទូរស័ព្ទ | **គ្មានសិទ្ធិ** Reset Queue ទាំងមូល, កែប្រែសេវាកម្ម ឬគ្រប់គ្រងគណនីអ្នកដទៃឡើយ (HTTP 403 Forbidden) |
| **អ្នកគ្រប់គ្រង (Admin)** | • ពេញសិទ្ធិលើប្រព័ន្ធទាំងមូល (Full Control)<br>• គ្រប់គ្រងបញ្ជីបុគ្គលិក និងបង្កើតគណនី Staff ថ្មីៗ (`/admin`)<br>• កែប្រែរយៈពេលបម្រើសេវាជាមធ្យម ដើម្បីផ្លាស់ប្តូររូបមន្តគណនា Smart ETA<br>• សិទ្ធិផ្តាច់មុខក្នុងការ Reset Queue ទាំងមូល (`/api/staff/reset-queue`) | ទាមទារគណនីកម្រិត Administrator |

### 🔑 គណនីគំរូសម្រាប់ Demo (Pre-seeded Accounts):
* **Admin**: Username: `admin` | Password: `admin123`
* **Staff 1**: Username: `staff1` | Password: `staff123` (បញ្ជរ ១)
* **Staff 2**: Username: `staff2` | Password: `staff123` (បញ្ជរ ២)
*(លើទំព័រ `/login` មានប៊ូតុង Quick Login សម្រាប់ចុចចូលសាកល្បងភ្លាមៗដោយមិនបាច់វាយអក្សរ)*

---

## 📁 ៥. រចនាសម្ព័ន្ធ Folder (Project Structure)

```text
Line_up_system/
├── app/
│   ├── __init__.py
│   ├── database.py           # SQLite connection & SQLAlchemy Session
│   ├── models.py             # Database Models (Service, User, QueueTicket)
│   ├── schemas.py            # Pydantic validation schemas
│   ├── queue_manager.py      # Core logic (ETA, Sequences, Call Next, Analytics)
│   ├── notifier.py           # WebSocket ConnectionManager & Telegram Bot
│   ├── main.py               # FastAPI App, Web Routes, API & WebSockets
│   ├── static/
│   │   ├── css/style.css     # Custom animations, ticket cutout style, fonts
│   │   └── js/queue_socket.js# WebSocket Client, Audio Synthesizer & TTS
│   └── templates/
│       ├── base.html         # Base layout with Tailwind & FontAwesome
│       ├── customer_ticket.html # Mobile customer portal
│       ├── staff_dashboard.html # Staff operations center
│       ├── tv_display.html   # Public TV display with sound & TTS
│       └── kiosk.html        # QR entrance kiosk
├── lineup.db                 # SQLite database file
├── test_app.py               # Automated test suite
├── requirements.txt          # Python dependencies
├── run.py                    # One-click startup script with LAN IP detection
└── README.md                 # Documentation
```

---

## 🌍 ៦. ការស្កេនឆ្លងបណ្តាញ (Cross-Network Scanning - មិនបាច់ប្រើ Wi-Fi ដូចគ្នា)

ប្រព័ន្ធបានបំពាក់នូវ **Cloudflare Tunnel (`cloudflared`)** ដែលអនុញ្ញាតឱ្យទូរស័ព្ទដៃរបស់អតិថិជន ឬគ្រូ **ស្កេន QR Code បានពីគ្រប់ទីកន្លែង ទោះបីជាប្រើ Wi-Fi ផ្សេងគ្នា ឬប្រើប្រព័ន្ធអ៊ីនធឺណិតទូរស័ព្ទ (4G / 5G Smart, Cellcard, Metfone)** ក៏ដោយ៖

* **ដំណើរការ Public Tunnel ស្វ័យប្រវត្តិ**:
  គ្រាន់តែ run៖
  ```bash
  python run.py
  ```
  ប្រព័ន្ធនឹងបង្កើត Public HTTPS URL មួយដោយស្វ័យប្រវត្តិ (ឧ. `https://xxxx.trycloudflare.com`)។
* **រូបភាព QR Code ឆ្លាតវៃ**:
  រូបភាព QR Code នៅលើផ្ទាំង TV Board (`/tv`) និង Kiosk (`/kiosk`) នឹង update ទៅជា Public HTTPS Link ភ្លាមៗ ធ្វើឱ្យទូរស័ព្ទណាស្កេនក៏អាចចូលយកលេខសំបុត្របានដោយជោគជ័យ ១០០%។
* **ជម្រើស Local-only**: ប្រសិនបើចង់ដំណើរការតែក្នុងបណ្តាញ Wi-Fi ផ្ទៃក្នុង៖ `python run.py --local`

---

## 📝 ៧. ការបំពេញព័ត៌មានជាកាតព្វកិច្ច (Mandatory Form Validation)

* **ឈ្មោះអតិថិជន (Customer Name)** និង **លេខទូរស័ព្ទ (Phone Number)** ត្រូវបានកំណត់ជា **កាតព្វកិច្ចដាច់ខាត (Required)**។
* ប្រសិនបើអតិថិជនមិនបំពេញ ឬបំពេញលេខទូរស័ព្ទតិចជាង ៨ ខ្ទង់ ប្រព័ន្ធនឹងបដិសេធមិនចេញសំបុត្រជួរឡើយ ដោយលោតសារដាស់តឿនជាភាសាខ្មែរ និងអង់គ្លេសទាំងនៅលើ Frontend និង Backend (HTTP 400 Validation)។

---

## 🔒 ៨. ការកំណត់សិទ្ធិមើលឃើញរបស់អតិថិជន (Customer View Exclusivity)

* នៅលើទំព័រ Customer (`/`):
  អតិថិជនមើលឃើញ **តែផ្ទាំងសំបុត្ររបស់ខ្លួនប៉ុណ្ណោះ**។ រាល់ Link និងប៊ូតុងទៅកាន់ Staff Dashboard, Admin Panel, TV Display, Kiosk ឬ Staff Login ត្រូវបាន **លាក់ទុកទាំងស្រុង**។
* ប្រសិនបើ Customer ព្យាយាមវាយ Link ចូល `/staff` ឬ `/admin` ដោយខ្លួនឯង ប្រព័ន្ធនឹង **Redirect ទៅកាន់ផ្ទាំង Login** ជាបន្ទាន់ និងការពារ API មិនឱ្យ Customer អាចហៅ ឬបញ្ជាជួរបានឡើយ។

---

## ⚙️ ៩. របៀបតម្លើង និងដំណើរការ (Installation & Setup)

### ជំហានទី ១: Install Dependencies
បើក Terminal / PowerShell ក្នុង Folder គម្រោង រួច run៖
```bash
pip install -r requirements.txt
```

### ជំហានទី ២: ដំណើរការប្រព័ន្ធ (Start System)
ដំណើរការ script `run.py`៖
```bash
python run.py
```

ប្រព័ន្ធនឹងស្វែងរក LAN IP របស់កុំព្យូទ័រអ្នកដោយស្វ័យប្រវត្តិ និងបង្ហាញផ្ទាំង Terminal ដូចខាងក្រោម៖
```text
=================================================================
 🚀 LineUp System - Smart Virtual Queue Management System
=================================================================
 [Customer Mobile App]    : http://192.168.1.16:8000/
 [Staff Dashboard]        : http://localhost:8000/staff
 [Public TV Display Board]: http://localhost:8000/tv
 [QR Code Kiosk]          : http://localhost:8000/kiosk
 [Swagger API Docs]       : http://localhost:8000/docs
-----------------------------------------------------------------
 💡 Tip for Presentation:
    Connect your mobile phone to the same Wi-Fi, then scan
    the QR code or navigate to: http://192.168.1.16:8000/
=================================================================
```

---

## 🎯 ៦. ការបង្ហាញ Demo ជាក់ស្តែងក្នុងថ្នាក់ (Presentation Guide)

ដើម្បីធ្វើឱ្យ Presentation របស់អ្នកទទួលបានពិន្ទុខ្ពស់ និងទាក់ទាញបំផុត សូមអនុវត្តតាមជំហានខាងក្រោម៖

1. **ភ្ជាប់ Wi-Fi តែមួយ**: ភ្ជាប់កុំព្យូទ័រ Laptop និងទូរស័ព្ទដៃរបស់គ្រូ ឬមិត្តភក្តិទៅកាន់ Wi-Fi តែមួយ (ឬបើក Mobile Hotspot ពីទូរស័ព្ទ)។
2. **បើកអេក្រង់ TV Display (`/tv`)**: បញ្ចាំងអេក្រង់នេះទៅលើ Projector ឬ TV ធំក្នុងថ្នាក់ រួចចុចលើអេក្រង់ដើម្បី **Unmute សំឡេង**។
3. **បើកអេក្រង់ Staff Dashboard (`/staff`)**: ដាក់លើ Laptop របស់សមាជិកក្រុមដែលដើរតួជាបុគ្គលិកបញ្ជរ (Counter 1)។
4. **អញ្ជើញគ្រូ ឬមិត្តភក្តិឱ្យស្កេន**:
   - ឱ្យគាត់យកទូរស័ព្ទមកស្កេន **QR Code** ដែលបង្ហាញលើ TV (`/tv`) ឬ Kiosk (`/kiosk`)។
   - គាត់នឹងទទួលបានសំបុត្រ **A-001** លើទូរស័ព្ទដៃរបស់គាត់ភ្លាមៗ។
   - សាកល្បងឱ្យសិស្សម្នាក់ទៀតយកសំបុត្រ **A-002** នោះទូរស័ព្ទរបស់គាត់នឹងបង្ហាញថា **Ahead: 1 នាក់, ETA: ~5 នាទី**។
5. **Staff ចុច "Call Next"**:
   - នៅលើ Laptop ពេលបុគ្គលិកចុច "Call Next"៖
     - អេក្រង់ Projector (`/tv`) នឹងលោតពន្លឺភ្លឹបភ្លែត បន្លឺសំឡេង **Ding-Dong** និងអានជាសំឡេង៖ *"Ticket A 0 0 1, please proceed to counter 1"*។
     - ទូរស័ព្ទរបស់គ្រូនឹង **ញ័រ (Vibrate)** និងលោតផ្ទាំងពណ៌ស្វាយថា៖ *"ដល់វេនរបស់អ្នកហើយ! សូមអញ្ជើញទៅកាន់ បញ្ជរលេខ ១"*។
6. **បង្ហាញមុខងារពិសេស**:
   - **No-Show Timer**: បង្ហាញ Timer រាប់ថយក្រោយ ៣ នាទី។
   - **Daily Statistics**: បង្ហាញក្រាហ្វិកស្ថិតិភ្ញៀវ និងម៉ោងរង់ចាំជាមធ្យមលើ Dashboard។

---

## 🧪 ៧. ការ Run Test ផ្ទៀងផ្ទាត់កូដ (Automated Testing)

អ្នកអាចធ្វើតេស្ត logic ទាំងអស់នៃប្រព័ន្ធបានគ្រប់ពេលដោយ run៖
```bash
python test_app.py
```
លទ្ធផលនឹងបង្ហាញ៖
`ALL TESTS PASSED SUCCESSFULLY! (100% OK)`

---

## 👨‍💻 ព័ត៌មានអ្នកអភិវឌ្ឍន៍ (Developer Information)
* **Project**: LineUp System - Smart Virtual Queue Management System
* **Academic Year**: Year 4 Capstone / Final Year Project
* **Language & Framework**: Python, FastAPI, WebSockets, Tailwind CSS, SQLite
