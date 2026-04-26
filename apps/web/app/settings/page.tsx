"use client";

import { useRouter } from "next/navigation";
import { useRequiredSession } from "@/lib/use-required-session";
import { exportUserData, deleteAccount } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import copy from "@/lib/copy.json";

export default function SettingsPage() {
  const router = useRouter();
  const { loading, token } = useRequiredSession();

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6 text-secondary">{copy.states.loading}</CardContent>
      </Card>
    );
  }

  if (!token) {
    return null;
  }

  async function handleExport() {
    try {
      const blob = await exportUserData(token!);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "spectraquant-data-export.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed", err);
    }
  }

  async function handleDeleteAccount() {
    const confirmed = window.confirm(
      "Are you sure? This will schedule deletion of all your data in 30 days."
    );
    if (!confirmed) return;

    try {
      await deleteAccount(token!);
      const supabase = getSupabaseBrowserClient();
      await supabase.auth.signOut();
      router.push("/login");
    } catch (err) {
      console.error("Account deletion failed", err);
    }
  }

  return (
    <section className="space-y-8 max-w-2xl">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-tertiary">Settings</p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">Account settings</h2>
      </div>

      {/* Export data */}
      <Card>
        <CardHeader>
          <CardTitle>Your data</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-secondary">
            Download everything SpectraQuant holds about your account in JSON format.
          </p>
          <Button variant="outline" onClick={handleExport}>
            Export data
          </Button>
        </CardContent>
      </Card>

      {/* Delete account */}
      <Card className="border-red-500/60">
        <CardHeader>
          <CardTitle className="text-red-400">Delete account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-secondary">
            Your data will be queued for deletion and permanently removed after 30 days. This cannot
            be undone.
          </p>
          <Button variant="destructive" onClick={handleDeleteAccount}>
            Schedule account deletion
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
