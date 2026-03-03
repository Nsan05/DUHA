import MapView from "@/components/MapView/MapView";
import TimeSelector from "@/components/TimeSelector/TimeSelector";
import BottomSheet from "@/components/BottomSheet/BottomSheet";

export default function Home() {
  return (
    <main>
      <TimeSelector />
      <MapView />
      <BottomSheet />
    </main>
  );
}
