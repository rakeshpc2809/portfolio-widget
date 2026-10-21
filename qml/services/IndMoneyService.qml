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
    property int schemaVersion: 2
    property string provider: "indmoney"
    property string status: "offline" // "ok", "partial", "error", "auth_required", "offline"
    property string freshness: "fresh" // "fresh", "aging", "stale", "partial", "auth_required"
    property string navAsOf: ""
    property string marketState: "CLOSED" // "IN_OPEN", "US_OPEN", "CLOSED", "CACHED"
    property var failedSources: []
    property string authError: ""
    property double lastUpdated: 0

    // Quiet Mode (F3): hides 1D change by default until hover/tap or toggle
    property bool quietMode: true
    property bool privacyMode: false
    readonly property bool syncing: syncProc.running

    // Schema v2 Domain Models
    property var investedPortfolio: ({
        current_value_inr: 0,
        invested_value_inr: 0,
        total_return_inr: 0,
        total_return_pct: 0,
        one_day_change_inr: 0,
        one_day_change_pct: 0
    })

    property var totalNetworth: ({
        total_networth_inr: 0,
        bank_balance_inr: 0,
        epf_inr: 0
    })

    property var buckets: []
    property var attentionItems: []
    property var holdings: []
    property var sips: ({
        monthly_total_inr: 0,
        monthly_total_usd: 0,
        active_count: 0,
        next_7d_sip_inr: 0,
        sip_coverage_ratio: 0,
        sip_coverage_ok: true,
        upcoming: []
    })
    property var sparkline90d: []
    property var portfolioOs: ({
        enabled: false,
        xirr_pct: null,
        rebalance_action: null
    })

    // Basis Consistency Convenience Getters (C8)
    readonly property real investedValue: investedPortfolio?.current_value_inr ?? 0
    readonly property real oneDayChangeInr: investedPortfolio?.one_day_change_inr ?? 0
    readonly property real oneDayChangePct: investedPortfolio?.one_day_change_pct ?? 0
    readonly property real totalReturnInr: investedPortfolio?.total_return_inr ?? 0
    readonly property real totalReturnPct: investedPortfolio?.total_return_pct ?? 0
    readonly property real networthValue: totalNetworth?.total_networth_inr ?? 0
    readonly property real bankBalanceValue: totalNetworth?.bank_balance_inr ?? 0
    readonly property real epfValue: totalNetworth?.epf_inr ?? 0

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

    function toggleQuietMode(): void {
        root.quietMode = !root.quietMode
    }

    function _applyState(rawText: string): void {
        if (!rawText || rawText.trim().length === 0) return
        try {
            const data = JSON.parse(rawText)
            if (!data) return

            root.schemaVersion = data.schema_version ?? 2
            root.provider = data.provider ?? "indmoney"
            root.status = data.status || "ok"
            root.freshness = data.freshness || "fresh"
            root.navAsOf = data.nav_as_of || ""
            root.marketState = data.market_state || "CLOSED"
            root.failedSources = Array.isArray(data.failed_sources) ? data.failed_sources : []
            root.authError = data.auth_error || ""
            root.lastUpdated = data.updated_at || (Date.now() / 1000)

            if (data.invested_portfolio) root.investedPortfolio = data.invested_portfolio
            else if (data.summary) {
                // Backward-compat v1 mapping
                root.investedPortfolio = {
                    current_value_inr: data.summary.total_portfolio_inr ?? data.summary.total_networth_inr ?? 0,
                    invested_value_inr: data.summary.invested_inr ?? 0,
                    total_return_inr: data.summary.total_pnl_inr ?? 0,
                    total_return_pct: data.summary.total_pnl_pct ?? 0,
                    one_day_change_inr: data.summary.day_change_inr ?? 0,
                    one_day_change_pct: data.summary.day_change_pct ?? 0
                }
            }

            if (data.total_networth) root.totalNetworth = data.total_networth
            else if (data.summary) {
                root.totalNetworth = {
                    total_networth_inr: data.summary.total_networth_inr ?? 0,
                    bank_balance_inr: data.summary.bank_inr ?? 0,
                    epf_inr: data.summary.epf_inr ?? 0
                }
            }

            if (Array.isArray(data.buckets)) root.buckets = data.buckets
            if (Array.isArray(data.attention_items)) root.attentionItems = data.attention_items
            if (Array.isArray(data.holdings)) root.holdings = data.holdings
            if (data.sips) root.sips = data.sips
            if (Array.isArray(data.sparkline_90d)) root.sparkline90d = data.sparkline_90d
            else if (Array.isArray(data.sparkline)) root.sparkline90d = data.sparkline
            if (data.portfolio_os) root.portfolioOs = data.portfolio_os

            root.ready = true
        } catch (e) {
            console.warn("[IndMoneyService] Error parsing state JSON:", e)
        }
    }

    // --- Currency & Value Formatting ---

    // Fixed-length mask (V5) that never leaks digit count
    readonly property string staticMask: "₹ ••••••"

    function formatInr(val: real, masked: bool): string {
        return formatInrFull(val, masked)
    }

    function formatCompactInr(val: real, masked: bool): string {
        return formatInrCompact(val, masked)
    }

    function formatInrCompact(val: real, masked: bool): string {
        if (masked || root.privacyMode) return root.staticMask
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
        if (masked || root.privacyMode) return root.staticMask
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
        if (!root.ready) {
            Quickshell.execDetached([root.syncBin, "hydrate"])
        }
    }
}
