"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { AuthChangeEvent, Session, User } from "@supabase/supabase-js";

import { getSupabaseBrowserClient } from "@/lib/supabase/client";

type SessionState = {
  loading: boolean;
  session: Session | null;
  user: User | null;
  token: string | null;
};

export function useRequiredSession() {
  const router = useRouter();
  const [state, setState] = useState<SessionState>({
    loading: true,
    session: null,
    user: null,
    token: null
  });

  useEffect(() => {
    let active = true;
    const supabase = getSupabaseBrowserClient();

    async function loadSession() {
      const { data } = await supabase.auth.getSession();
      if (!active) {
        return;
      }

      if (!data.session) {
        router.replace("/login");
        setState({ loading: false, session: null, user: null, token: null });
        return;
      }

      setState({
        loading: false,
        session: data.session,
        user: data.session.user,
        token: data.session.access_token
      });
    }

    void loadSession();

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange(
      (_event: AuthChangeEvent, session: Session | null) => {
        if (!active) {
          return;
        }
        if (!session) {
          router.replace("/login");
          setState({ loading: false, session: null, user: null, token: null });
          return;
        }
        setState({
          loading: false,
          session,
          user: session.user,
          token: session.access_token
        });
      }
    );

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [router]);

  return state;
}
