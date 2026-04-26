"use client";

import { useQuery } from "@tanstack/react-query";
import { useRequiredSession } from "@/lib/use-required-session";
import { getAdminJobs, type JobRun } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import copy from "@/lib/copy.json";

function formatIST(isoString: string): string {
  return new Date(isoString).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function durationSeconds(started: string, finished: string | null): string {
  if (!finished) return "—";
  const ms = new Date(finished).getTime() - new Date(started).getTime();
  return `${(ms / 1000).toFixed(1)}s`;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "success") {
    return (
      <Badge className="bg-green-600/20 text-green-400 border-green-600/30 hover:bg-green-600/20">
        success
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge className="bg-red-600/20 text-red-400 border-red-600/30 hover:bg-red-600/20">
        failed
      </Badge>
    );
  }
  return (
    <Badge className="bg-yellow-600/20 text-yellow-400 border-yellow-600/30 hover:bg-yellow-600/20">
      {status}
    </Badge>
  );
}

export default function AdminJobsPage() {
  const { loading, token } = useRequiredSession();

  const jobsQuery = useQuery({
    queryKey: ["admin-jobs", token],
    queryFn: async () => getAdminJobs(token ?? ""),
    enabled: Boolean(token),
    refetchInterval: 30_000,
    retry: (failureCount, error) => {
      if ((error as Error).message.includes("403")) return false;
      return failureCount < 2;
    },
  });

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

  const is403 =
    jobsQuery.isError && (jobsQuery.error as Error).message.includes("403");

  if (is403) {
    return (
      <Card>
        <CardContent className="p-6 text-secondary">
          Access restricted to the founder account.
        </CardContent>
      </Card>
    );
  }

  const jobs: JobRun[] = jobsQuery.data?.jobs ?? [];

  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-tertiary">Admin</p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">Job run history</h2>
        <p className="mt-2 text-sm text-secondary">
          Refreshes every 30 seconds automatically.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {jobsQuery.isLoading ? (
            <p className="p-6 text-sm text-secondary">{copy.states.loading}</p>
          ) : jobs.length === 0 ? (
            <p className="p-6 text-sm text-secondary">No job runs recorded yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Rows written</TableHead>
                  <TableHead>Started (IST)</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job, idx) => (
                  <TableRow key={`${job.job_name}-${job.started_at}-${idx}`}>
                    <TableCell className="font-mono text-sm">{job.job_name}</TableCell>
                    <TableCell>
                      <StatusBadge status={job.status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {job.rows_written ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm">{formatIST(job.started_at)}</TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {durationSeconds(job.started_at, job.finished_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
