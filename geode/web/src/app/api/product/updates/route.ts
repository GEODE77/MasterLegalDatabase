import {
  getProductApiSummary,
  getProductUpdates,
  getUpdateLedger,
  getUpdateLedgerSummary,
} from "@/lib/product/productIndex";

export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({
    ledger: getUpdateLedger(100),
    summary: getProductApiSummary(),
    updateLedgerSummary: getUpdateLedgerSummary(),
    updates: getProductUpdates(),
  });
}
