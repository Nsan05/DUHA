import MapView from "@/components/MapView/MapView";
import TimeSelector from "@/components/TimeSelector/TimeSelector";

export default function Home() {
  return (
    <main>
      <TimeSelector />
      <MapView />
    </main>
  );
}
