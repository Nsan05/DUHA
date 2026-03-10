import MapView from "@/components/MapView/MapView";
import TimeSelector from "@/components/TimeSelector/TimeSelector";
import BottomSheet from "@/components/BottomSheet/BottomSheet";
import HintToast from "@/components/HintToast/HintToast";

export default function Home() {
  return (
    <main>
      <TimeSelector />
      <HintToast />
      <MapView />
      <BottomSheet />
    </main>
  );
}
