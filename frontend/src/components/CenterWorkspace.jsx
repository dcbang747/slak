import { useStore } from '../store';
import GlobalSettings from './views/GlobalSettings';
import LifeCycleModifiers from './views/LifeCycleModifiers';
import TitleHistories from './views/TitleHistories';
import FamilyTree from './views/FamilyTree';

const VIEWS = {
  global: GlobalSettings,
  lifecycle: LifeCycleModifiers,
  titles: TitleHistories,
  tree: FamilyTree,
};

export default function CenterWorkspace() {
  const { active_view } = useStore();
  const View = VIEWS[active_view] ?? GlobalSettings;
  return (
    <main className="flex-1 overflow-y-auto bg-white dark:bg-gray-900 p-8">
      <View />
    </main>
  );
}
