import React from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { getDomainConfig } from "@/lib/domain";

export default function RootLayout() {
  const cfg = getDomainConfig();
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#164e8a" },
          headerTintColor: "#ffffff",
          headerTitleStyle: { fontWeight: "600" },
        }}
      >
        <Stack.Screen name="index" options={{ title: cfg.display_name }} />
        <Stack.Screen name="cheap-intervals" options={{ title: "Cheap intervals" }} />
        <Stack.Screen name="alerts" options={{ title: "Alerts" }} />
      </Stack>
    </>
  );
}
