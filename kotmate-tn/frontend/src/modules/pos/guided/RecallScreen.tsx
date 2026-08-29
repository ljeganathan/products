import { RecallList } from "@/modules/pos/RecallList";

interface RecallScreenProps {
  locationId: string | null;
  onSelectOrder: (orderId: string) => void;
}

// Full-screen version of the real RecallPanel — same held-bills list, no popup
// chrome (round-2 feedback: Recall should be a rail area like Fast Billing, not a
// modal).
export function RecallScreen({ locationId, onSelectOrder }: RecallScreenProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl">
        <h2 className="mb-4 text-lg font-extrabold">↺ Recall Bill</h2>
        {locationId ? (
          <RecallList locationId={locationId} onSelectOrder={onSelectOrder} />
        ) : (
          <p className="text-sm text-ink-faint">Select a location first.</p>
        )}
      </div>
    </div>
  );
}
