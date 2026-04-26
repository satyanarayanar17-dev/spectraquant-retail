"use client";

import { FormEvent, useState } from "react";

import copy from "@/lib/copy.json";
import { track } from "@/lib/analytics";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("loading");

    const supabase = getSupabaseBrowserClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/dashboard`
      }
    });

    if (!error) track("signup_completed");
    setStatus(error ? "error" : "success");
  }

  return (
    <div className="grid min-h-[72vh] place-items-center">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <p className="text-xs uppercase tracking-[0.24em] text-tertiary">
            {copy.login.eyebrow}
          </p>
          <CardTitle className="text-2xl">{copy.login.title}</CardTitle>
          <CardDescription>{copy.login.subtitle}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="email">{copy.login.emailLabel}</Label>
              <Input
                id="email"
                type="email"
                placeholder={copy.login.emailPlaceholder}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <Button className="w-full" type="submit" disabled={status === "loading"}>
              {status === "loading" ? copy.login.submitting : copy.login.submit}
            </Button>
            {status === "success" ? (
              <p className="text-sm text-pos">{copy.login.success}</p>
            ) : null}
            {status === "error" ? (
              <p className="text-sm text-neg">{copy.login.error}</p>
            ) : null}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
