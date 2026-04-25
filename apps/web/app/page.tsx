"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import copy from "@/lib/copy.json";
import { Card, CardContent } from "@/components/ui/card";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();

    async function resolveSession() {
      const { data } = await supabase.auth.getSession();
      router.replace(data.session ? "/dashboard" : "/login");
    }

    void resolveSession();
  }, [router]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card className="w-full max-w-md">
        <CardContent className="p-6 text-center text-secondary">
          {copy.states.checkingSession}
        </CardContent>
      </Card>
    </div>
  );
}
