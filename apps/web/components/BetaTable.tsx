import copy from "@/lib/copy.json";
import type { AttributionResult } from "@/lib/api";
import { FACTOR_LABELS } from "@/lib/factors";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";

type BetaTableProps = {
  result: AttributionResult;
};

export function BetaTable({ result }: BetaTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.betaTable.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{copy.betaTable.factor}</TableHead>
              <TableHead>{copy.betaTable.beta}</TableHead>
              <TableHead>{copy.betaTable.se}</TableHead>
              <TableHead>{copy.betaTable.ci}</TableHead>
              <TableHead>{copy.betaTable.pvalue}</TableHead>
              <TableHead>{copy.betaTable.significance}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(result.betas).map(([factor, beta]) => (
              <TableRow key={factor}>
                <TableCell>{FACTOR_LABELS[factor as keyof typeof FACTOR_LABELS] ?? factor}</TableCell>
                <TableCell className="font-mono">{beta.beta.toFixed(3)}</TableCell>
                <TableCell className="font-mono">{beta.se.toFixed(3)}</TableCell>
                <TableCell className="font-mono">
                  {beta.ci_low.toFixed(3)} to {beta.ci_high.toFixed(3)}
                </TableCell>
                <TableCell className="font-mono">{beta.pvalue.toFixed(4)}</TableCell>
                <TableCell>
                  <Badge variant={beta.significant ? "success" : "muted"}>
                    {beta.significant
                      ? copy.betaTable.significant
                      : copy.betaTable.notSignificant}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
