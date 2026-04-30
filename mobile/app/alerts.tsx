import React, { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { getDomainConfig } from "@/lib/domain";
import { Alert, getAlerts, PulseApiError } from "@/lib/api";
import { formatHourMinuteUtc, formatPrice } from "@/lib/format";

export default function AlertsScreen() {
  const cfg = getDomainConfig();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getAlerts(cfg.default_region)
      .then((data) => {
        if (!cancelled) setAlerts(data.alerts);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof PulseApiError ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cfg.default_region]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.errorBox}>
        <Text style={styles.errorTitle}>Could not load alerts</Text>
        <Text style={styles.errorDetail}>{error}</Text>
      </View>
    );
  }

  if (alerts.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.empty}>No alerts have fired for {cfg.default_region} yet.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={alerts}
      keyExtractor={(a) => String(a.id)}
      renderItem={({ item }) => (
        <View style={styles.row}>
          <View style={{ flex: 1 }}>
            <Text style={styles.dateText}>{item.price_date}</Text>
            <Text style={styles.peakText}>
              peak {formatHourMinuteUtc(item.peak_interval_start)} UTC ·{" "}
              {formatPrice(item.peak_c_kwh)} c/kWh
            </Text>
          </View>
          <Text style={styles.thresholdText}>
            threshold {formatPrice(item.threshold_c_kwh)}
          </Text>
        </View>
      )}
      contentContainerStyle={styles.list}
      style={styles.container}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  list: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 32 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 16 },
  empty: { color: "#64748b" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  dateText: { fontWeight: "600", color: "#0f172a" },
  peakText: { fontSize: 12, color: "#475569", marginTop: 2 },
  thresholdText: { color: "#475569", fontSize: 12 },
  errorBox: {
    backgroundColor: "#fee2e2",
    borderColor: "#fecaca",
    borderWidth: 1,
    padding: 12,
    borderRadius: 6,
    margin: 16,
  },
  errorTitle: { color: "#991b1b", fontWeight: "600" },
  errorDetail: { color: "#7f1d1d", marginTop: 4, fontSize: 12 },
});
