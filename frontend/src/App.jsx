import { useStore } from './store';
import LeftSidebar from './components/LeftSidebar';
import CenterWorkspace from './components/CenterWorkspace';
import RightDrawer from './components/RightDrawer';

export default function App() {
  const dark_mode = useStore((s) => s.dark_mode);
  // 'dark' on this div drives all dark: descendant variants.
  // bg- is set directly (not via dark: variant) since this IS the .dark element.
  return (
    <div className={`h-full flex ${dark_mode ? 'dark bg-gray-900' : 'bg-white'}`}>
      <LeftSidebar />
      <CenterWorkspace />
      <RightDrawer />
    </div>
  );
}
