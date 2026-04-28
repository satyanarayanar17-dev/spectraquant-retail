/** @type {import('next').NextConfig} */
const nextConfig = {
  // Bridge server-side env vars into the client bundle.
  //
  // The Supabase "anon" key is designed to be public — it's a JWT for the
  // anonymous role and security is enforced server-side via RLS. Some
  // deployments only set SUPABASE_ANON_KEY (server convention); fall back
  // to that when NEXT_PUBLIC_SUPABASE_ANON_KEY isn't explicitly defined.
  // Same idea for the Supabase URL.
  //
  // Next inlines these at build time, so the values shipped to the browser
  // are baked into the static chunks.
  env: {
    NEXT_PUBLIC_SUPABASE_URL:
      process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY:
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? process.env.SUPABASE_ANON_KEY,
  },
};

export default nextConfig;
