import React, { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { getDomainConfig } from "@/lib/domain";
import {
  getCheapIntervals,
  PulseApiError,
  RankedInterval,
} from "@/lib/api";
import { formatHourMinuteUtc, formatPrice } from "@/lib/format";

export default function CheapIntervalsScreen() {
  const cfg = getDomainConfig();
  const [rows, setRows] = useState<RankedInterval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCheapIntervals(cfg.default_region, "today", 10)
      .then((data) => {
        if (!cancelled) setRows(data.intervals);
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
        <Text style={styles.errorTitle}>Could not load cheap intervals</Text>
        <Text style={styles.errorDetail}>{error}</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={rows}
      keyExtractor={(r) => r.interval_start}
      renderItem={({ item }) => (
        <View style={styles.row}>
          <Text style={styles.rank}>#{item.rank}</Text>
          <Text style={styles.cellTime}>
            {formatHourMinuteUtc(item.interval_start)}–{formatHourMinuteUtc(item.interval_end)}
          </Text>
          <Text style={styles.cellTotal}>{formatPrice(item.total_c_kwh)} c/kWh</Text>
        </View>
      )}
      ListHeaderComponent={
        <View style={[styles.row, styles.headerRow]}>
          <Text style={[styles.rank, styles.headerText]}>Rank</Text>
          <Text style={[styles.cellTime, styles.headerText]}>Window (UTC)</Text>
          <Text style={[styles.cellTotal, styles.headerText]}>total c/kWh</Text>
        </View>
      }
      contentContainerStyle={styles.list}
      style={styles.container}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8fafc" },
  list: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 32 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  row: {
    flexDirection: "row",
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  headerRow: { borderBottomWidth: 2, borderBottomColor: "#cbd5e1", backgroundColor: "#f1f5f9" },
  headerText: { fontWeight: "600", color: "#334155" },
  rank: { width: 48, fontWeight: "600" },
  cellTime: { flex: 1, fontVariant: ["tabular-nums"], fontFamily: "Menlo" },
  cellTotal: { flex: 1, textAlign: "right", fontWeight: "600" },
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
