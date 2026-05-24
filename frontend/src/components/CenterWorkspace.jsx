import { useStore } from '../store';
import GlobalSettings from './views/GlobalSettings';
import LifeCycleModifiers from './views/LifeCycleModifiers';
import TitleHistories from './views/TitleHistories';
import FamilyTree from './views/FamilyTree';
import JamieGenerator from './views/JamieGenerator';

const VIEWS = {
  global: GlobalSettings,
  lifecycle: LifeCycleModifiers,
  titles: TitleHistories,
  tree: FamilyTree,
  jamie: JamieGenerator,
};

export default function CenterWorkspace() {
  const { active_view, app_mode } = useStore();
  // In Jamie mode the only non-tree view is the linear generator form.
  const view = app_mode === 'jamie' && active_view !== 'tree' ? 'jamie' : active_view;
  const View = VIEWS[view] ?? GlobalSettings;
  return (
    <main className="flex-1 overflow-y-auto bg-white dark:bg-gray-900 p-8">
      <View />
    </main>
  );
}
