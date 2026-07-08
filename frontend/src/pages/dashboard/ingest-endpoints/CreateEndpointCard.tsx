import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface CreateEndpointCardProps {
  name: string;
  setName: (value: string) => void;
  onCreate: () => void;
}

export function CreateEndpointCard({
  name,
  setName,
  onCreate,
}: CreateEndpointCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="text-sm font-semibold">Create endpoint</div>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1 space-y-2">
          <Label htmlFor="create-endpoint-name">Name</Label>
          <Input
            id="create-endpoint-name"
            name="name"
            autoComplete="off"
            placeholder="Primary endpoint"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <Button className="sm:shrink-0" disabled={!name.trim()} onClick={onCreate}>
          Create
        </Button>
      </div>
    </div>
  );
}
