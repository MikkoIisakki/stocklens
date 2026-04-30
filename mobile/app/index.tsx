import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Link } from "expo-router";
import { getDomainConfig } from "@/lib/domain";
import { getPrices, IntervalPrice, PulseApiError } from "@/lib/api";
import { formatHourMinuteUtc, formatPrice } from "@/lib/format";

export default function PricesScreen() {
  const cfg = getDomainConfig();
  const [prices, setPrices] = useState<IntervalPrice[]>([]);
  const [meta, setMeta] = useState<{ region: string; date: string; mins: number | null }>({
    region: cfg.default_region,
    date: "today",
    mins: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPrices(cfg.default_region, "today")
      .then((data) => {
        if (cancelled) return;
        setPrices(data.prices);
        setMeta({ region: data.region, date: data.date, mins: data.interval_minutes });
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

  return (
    <View style={styles.container}>
      <Text style={styles.subtitle}>{cfg.description}</Text>
      <Text style={styles.meta}>
        {meta.region} · {meta.date}
        {meta.mins ? ` · ${meta.mins}-min` : ""}
      </Text>

      <View style={styles.nav}>
        <Link href="/cheap-intervals" asChild>
          <Pressable style={styles.navButton}>
            <Text style={styles.navButtonText}>Cheap intervals</Text>
          </Pressable>
        </Link>
        <Link href="/alerts" asChild>
          <Pressable style={styles.navButton}>
            <Text style={styles.navButtonText}>Alerts</Text>
          </Pressable>
        </Link>
      </View>

      {loading ? (
        <ActivityIndicator size="large" style={styles.loader} />
      ) : error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorTitle}>Could not load prices</Text>
          <Text style={styles.errorDetail}>{error}</Text>
        </View>
      ) : (
        <FlatList
          data={prices}
          keyExtractor={(p) => p.interval_start}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <Text style={styles.cellTime}>{formatHourMinuteUtc(item.interval_start)}</Text>
              <Text style={styles.cellSpot}>{formatPrice(item.spot_c_kwh)}</Text>
              <Text style={styles.cellTotal}>{formatPrice(item.total_c_kwh)}</Text>
            </View>
          )}
          ListHeaderComponent={
            <View style={[styles.row, styles.headerRow]}>
              <Text style={[styles.cellTime, styles.headerText]}>UTC</Text>
              <Text style={[styles.cellSpot, styles.headerText]}>spot c/kWh</Text>
              <Text style={[styles.cellTotal, styles.headerText]}>total c/kWh</Text>
            </View>
          }
          contentContainerStyle={styles.list}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, paddingHorizontal: 16, paddingTop: 8, backgroundColor: "#f8fafc" },
  subtitle: { color: "#475569", fontSize: 14 },
  meta: { color: "#64748b", fontSize: 12, marginTop: 4 },
  nav: { flexDirection: "row", gap: 8, marginVertical: 12 },
  navButton: {
    backgroundColor: "#164e8a",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  navButtonText: { color: "#ffffff", fontSize: 13, fontWeight: "500" },
  loader: { marginTop: 32 },
  list: { paddingBottom: 32 },
  row: {
    flexDirection: "row",
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  headerRow: { borderBottomWidth: 2, borderBottomColor: "#cbd5e1", backgroundColor: "#f1f5f9" },
  headerText: { fontWeight: "600", color: "#334155" },
  cellTime: { flex: 1, fontVariant: ["tabular-nums"], fontFamily: "Menlo" },
  cellSpot: { flex: 1, textAlign: "right" },
  cellTotal: { flex: 1, textAlign: "right", fontWeight: "600" },
  errorBox: {
    backgroundColor: "#fee2e2",
    borderColor: "#fecaca",
    borderWidth: 1,
    padding: 12,
    borderRadius: 6,
    marginTop: 16,
  },
  errorTitle: { color: "#991b1b", fontWeight: "600" },
  errorDetail: { color: "#7f1d1d", marginTop: 4, fontSize: 12 },
});
