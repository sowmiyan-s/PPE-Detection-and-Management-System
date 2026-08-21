import React, { useState, useEffect } from "react";
import { Bell, Send, CheckCircle2, AlertTriangle, Loader2, ShieldCheck, ExternalLink } from "lucide-react";
import { useToast } from "@/lib/toast-context";

export function DiscordWebhookSettings() {
  const { showToast } = useToast();
  const [enabled, setEnabled] = useState<boolean>(false);
  const [webhookUrl, setWebhookUrl] = useState<string>("");
  const [minConfidence, setMinConfidence] = useState<number>(0.50);
  const [loadingConfig, setLoadingConfig] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);

  useEffect(() => {
    fetch("/api/webhook/config")
      .then((res) => (res.ok ? res.json() : {}))
      .then((data: any) => {
        if (data) {
          setEnabled(Boolean(data.enabled));
          setWebhookUrl(data.url || "");
          if (typeof data.min_confidence === "number") {
            setMinConfidence(data.min_confidence);
          }
        }
      })
      .catch((err) => console.error("Failed to load webhook config", err))
      .finally(() => setLoadingConfig(false));
  }, []);

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch("/api/webhook/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled,
          url: webhookUrl.trim(),
          min_confidence: minConfidence,
        }),
      });
      if (!res.ok) throw new Error("Failed to save Discord webhook settings");
      showToast(
        enabled
          ? "Discord Webhook alerts ENABLED and saved to database"
          : "Discord Webhook alerts DISABLED and saved to database"
      );
    } catch (err) {
      console.error("Save webhook error", err);
      showToast("Failed to save Discord webhook settings");
    } finally {
      setSaving(false);
    }
  };

  const handleSendTest = async () => {
    if (!webhookUrl.trim()) {
      showToast("Please enter a Discord Webhook URL first");
      return;
    }
    setTesting(true);
    try {
      const res = await fetch("/api/webhook/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: webhookUrl.trim() }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("✅ Test alert sent successfully to Discord channel!");
      } else {
        showToast(`❌ ${data.message || "Failed to send Discord test alert"}`);
      }
    } catch (err) {
      console.error("Test webhook error", err);
      showToast("❌ Network error connecting to Discord Webhook");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="relative overflow-hidden rounded panel-surface border border-border/80 p-5 shadow-md">
      <div className="hazard-stripe absolute inset-x-0 top-0 h-1 opacity-60" />
      
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Bell className="size-5" />
          </div>
          <div>
            <h3 className="display-title text-base font-bold flex items-center gap-2">
              Discord Webhook Alerts
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                  enabled && webhookUrl
                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    : "bg-muted/40 text-muted-foreground border border-border/50"
                }`}
              >
                <span className={`size-1.5 rounded-full ${enabled && webhookUrl ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground"}`} />
                {enabled && webhookUrl ? "Active" : "Disabled"}
              </span>
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Send real-time rich embed alert cards to your Discord channel when safety violations occur.
            </p>
          </div>
        </div>

        {/* Master ON/OFF Switch */}
        <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-border/80 bg-background/50 px-3 py-1.5 transition-colors hover:bg-background/80">
          <span className="text-xs font-semibold select-none">
            {enabled ? "Notifications ON" : "Notifications OFF"}
          </span>
          <input
            type="checkbox"
            className="sr-only"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <span
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
              enabled ? "bg-indigo-600" : "bg-muted"
            }`}
          >
            <span
              className={`absolute top-1 size-4 rounded-full bg-white transition-all ${
                enabled ? "left-6" : "left-1"
              }`}
            />
          </span>
        </label>
      </div>

      {loadingConfig ? (
        <div className="py-8 text-center text-xs text-muted-foreground animate-pulse">
          Loading Discord Webhook configuration...
        </div>
      ) : (
        <form onSubmit={handleSave} className="mt-4 space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-foreground">Discord Webhook URL</label>
              <a
                href="https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks"
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-indigo-400 hover:underline flex items-center gap-1"
              >
                <span>How to create a Discord webhook</span>
                <ExternalLink className="size-3" />
              </a>
            </div>
            <input
              type="url"
              placeholder="https://discord.com/api/webhooks/1234567890/..."
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/60 px-3 py-2 text-xs outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold mb-1 text-foreground">
                Minimum Alert Confidence Floor: <span className="text-indigo-400">{Math.round(minConfidence * 100)}%</span>
              </label>
              <input
                type="range"
                min={0.40}
                max={0.95}
                step={0.05}
                value={minConfidence}
                onChange={(e) => setMinConfidence(Number(e.target.value))}
                className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-muted accent-indigo-500"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                Only trigger Discord notifications if violation detection confidence exceeds {Math.round(minConfidence * 100)}%.
              </p>
            </div>

            <div className="rounded border border-border/50 bg-background/30 p-3 text-xs space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-muted-foreground text-[11px]">
                <ShieldCheck className="size-3.5 text-indigo-400" />
                <span>Payload Standard</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Includes Worker ID, Zone, Camera ID, missing PPE items, confidence score, and timestamp embed.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2 pt-3 border-t border-border/60">
            <button
              type="button"
              disabled={testing || !webhookUrl.trim()}
              onClick={handleSendTest}
              className="flex items-center gap-1.5 rounded border border-indigo-500/30 bg-indigo-500/10 px-3 py-1.5 text-xs font-semibold text-indigo-400 hover:bg-indigo-500 hover:text-white transition-colors disabled:opacity-50 cursor-pointer"
            >
              {testing ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
              <span>{testing ? "Sending Test..." : "Send Test Notification"}</span>
            </button>

            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-1.5 rounded bg-indigo-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-indigo-500 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
            >
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
              <span>{saving ? "Saving..." : "Save Webhook Settings"}</span>
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
