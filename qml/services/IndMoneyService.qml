pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import qs.modules.common

Singleton {
    id: root

    readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR") || ("/run/user/" + SystemInfo.userId)
    readonly property string statePath: root.runtimeDir + "/inir-indmoney/state.json"
    readonly property string syncBin: Directories.homePath + "/.local/bin/indmoney-sync"

    property bool ready: false
    property string status: "offline" // "ok", "syncing", "auth_required", "offline", "error", "cached"
    property string marketState: "CLOSED" // "IN_OPEN", "US_OPEN", "CLOSED", "CACHED"
    property string authError: ""
    property double lastUpdated: 0

    property var summary: ({
        total_portfolio_inr: 0,
        total_networth_inr: 0,
        bank_inr: 0,
        epf_inr: 0,
        non_investment_inr: 0,
        invested_inr: 0,
        total_pnl_inr: 0,
        total_pnl_pct: 0,
        day_change_inr: 0,
        day_change_pct: 0
    })

    property var allocation: []
    property var topMovers: []
    property var holdings: []
    property var sips: ({
        monthly_total_inr: 0,
        active_count: 0,
        next_7d_sip_inr: 0,
        sip_coverage_ok: true,
        upcoming: []
    })
    property var sparkline: []

    property bool privacyMode: false
    readonly property bool syncing: syncProc.running

    FileView {
        id: stateWatcher
        path: root.statePath
        watchChanges: true
        printErrors: false
        onLoaded: root._applyState(stateWatcher.text())
        onFileChanged: {
            stateWatcher.reload()
            root._applyState(stateWatcher.text())
        }
        onLoadFailed: error => {
            // Cold-boot: if state.json does not exist in tmpfs, trigger immediate hydration from encrypted keyring
            if (!root.ready) {
                Quickshell.execDetached([root.syncBin, "hydrate"])
            }
        }
    }

    Process {
        id: syncProc
        command: [root.syncBin, "fetch", "--force"]
        onExited: (exitCode, exitStatus) => {
            stateWatcher.reload()
        }
    }

    // Process lifetime guard: abort if process does not finish within 30 seconds
    Timer {
        id: syncTimeoutGuard
        interval: 30000
        repeat: false
        running: syncProc.running
        onTriggered: {
            if (syncProc.running) {
                console.warn("[IndMoneyService] Sync process timed out after 30s, resetting state.")
                syncProc.running = false
            }
        }
    }

    function refresh(): void {
        if (!syncProc.running) {
            syncProc.running = true
        }
    }

    function reauthenticate(): void {
        Quickshell.execDetached([root.syncBin, "auth"])
    }

    function togglePrivacy(): void {
        root.privacyMode = !root.privacyMode
    }

    function _applyState(rawText: string): void {
        if (!rawText || rawText.trim().length === 0) return
        try {
            const data = JSON.parse(rawText)
            if (!data) return

            root.status = data.status || "ok"
            root.marketState = data.market_state || "CLOSED"
            root.authError = data.auth_error || ""
            root.lastUpdated = data.updated_at || Date.now() / 1000

            if (data.summary) root.summary = data.summary
            if (Array.isArray(data.allocation)) root.allocation = data.allocation
            if (Array.isArray(data.top_movers)) root.topMovers = data.top_movers
            if (Array.isArray(data.holdings)) root.holdings = data.holdings
            if (data.sips) root.sips = data.sips
            if (Array.isArray(data.sparkline)) root.sparkline = data.sparkline

            root.ready = true
        } catch (e) {
            console.warn("[IndMoneyService] Error parsing state JSON:", e)
        }
    }

    // --- Currency & Value Formatting ---

    function formatInrCompact(val: real, masked: bool): string {
        if (masked) return "₹••.••L"
        if (val === undefined || isNaN(val)) return "₹0.00"

        const absVal = Math.abs(val)
        const sign = val < 0 ? "-" : ""

        if (absVal >= 10000000) { // 1 Crore
            return sign + "₹" + (absVal / 10000000).toFixed(2) + "Cr"
        } else if (absVal >= 100000) { // 1 Lakh
            return sign + "₹" + (absVal / 100000).toFixed(2) + "L"
        } else if (absVal >= 1000) { // 1 Thousand
            return sign + "₹" + (absVal / 1000).toFixed(1) + "K"
        }
        return sign + "₹" + absVal.toFixed(0)
    }

    function formatInrFull(val: real, masked: bool): string {
        if (masked) return "₹•••••••"
        if (val === undefined || isNaN(val)) return "₹0"

        const sign = val < 0 ? "-" : ""
        const parts = Math.abs(val).toFixed(0).split(".")
        let intPart = parts[0]

        // Indian Numbering grouping: last 3 digits, then groups of 2
        let lastThree = intPart.substring(intPart.length - 3)
        let otherNumbers = intPart.substring(0, intPart.length - 3)
        if (otherNumbers !== "") {
            lastThree = "," + lastThree
            otherNumbers = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",")
        }
        return sign + "₹" + otherNumbers + lastThree
    }

    function formatPct(val: real): string {
        if (val === undefined || isNaN(val)) return "0.00%"
        const sign = val > 0 ? "+" : ""
        return sign + Number(val).toFixed(2) + "%"
    }

    Component.onCompleted: {
        stateWatcher.reload()
        // If state is not loaded immediately at millisecond 0, request instant hydration
        if (!root.ready) {
            Quickshell.execDetached([root.syncBin, "hydrate"])
        }
    }
}
