import MapView from "@/components/MapView/MapView";
import TimeSelector from "@/components/TimeSelector/TimeSelector";
import BottomSheet from "@/components/BottomSheet/BottomSheet";
import HintToast from "@/components/HintToast/HintToast";
import DuhaLogo from "@/components/DuhaLogo/DuhaLogo";

export default function Home() {
  return (
    <main>
      <DuhaLogo />
      <TimeSelector />
      <HintToast />
      <MapView />
      <BottomSheet />
    </main>
  );
}
