// 果园害鸟图鉴静态数据:与 backend/detector.py 的 NAMES 13 类一一对应(en=模型原始标签)。
// 分级与文案为科普性整理(预览批次 docs/ui-flow/guide.html 定稿方向),封面图运行时取自本园真实抓拍
// (/api/library 的 alarm_groups.cover),从未检出的物种用剪影占位。
export type GuideLevel = 'high' | 'mid' | 'low'

export type SpeciesInfo = {
  name: string
  en: string
  level: GuideLevel
  desc: string
  harm: string
  traits: string
  hours: string
  advice: string
}

export const LEVEL_META: Record<GuideLevel, { label: string; groupTitle: string }> = {
  high: { label: '高危害', groupTitle: '主要害鸟 · 7 种' },
  mid: { label: '偶发采食', groupTitle: '偶发采食 · 4 种' },
  low: { label: '基本无害', groupTitle: '基本无害 · 2 种' },
}

export const SPECIES_GUIDE: SpeciesInfo[] = [
  {
    name: '八哥', en: 'Crested Myna', level: 'high',
    desc: '成群啄开果皮取食，被啄果实易腐坏',
    harm: '成群活动，啄开果皮取食果肉，被啄破的果实极易二次腐坏；果实成熟期损失最大，是本园重点驱防对象。',
    traits: '通体黑亮带金属光泽，飞行时翼上可见明显白斑，集群停落时鸣叫喧闹。',
    hours: '昼间活动，清晨与傍晚最活跃，常成群往返果园与林地。',
    advice: '检出即告警；声波 / 双模驱离对集群个体有效，驱散后短期不易回巢。',
  },
  {
    name: '白喉红臀鹎', en: 'Sooty-headed Bulbul', level: 'high',
    desc: '嗜食成熟浆果，啄破后果串易整串腐坏',
    harm: '嗜食成熟浆果，啄破果皮后汁液外流，整串果实容易霉变腐坏，挂果期危害集中。',
    traits: '头顶深灰，喉部白斑与橙红色臀部明显，喜停在树冠上层。',
    hours: '昼间，晨昏觅食最活跃。',
    advice: '检出即告警；果实成熟期建议保持双模待机。',
  },
  {
    name: '大嘴乌鸦', en: 'Large-billed Crow', level: 'high',
    desc: '体型大且机警，啄食并叼走果实',
    harm: '体型大、警觉性高，啄食果实并直接叼走，单只破坏量大；受惊后较长时间回避同一地点。',
    traits: '全身黑色，喙粗大呈弧形，额部隆起，常单独或成对活动。',
    hours: '昼间，清晨与午后活动。',
    advice: '检出即告警；对单一声波适应快，建议双模并轮换时长。',
  },
  {
    name: '树麻雀', en: 'Eurasian Tree Sparrow', level: 'high',
    desc: '数量多、贴近树冠，啄食嫩芽与幼果',
    harm: '数量多、活动贴近树冠，啄食嫩芽、种子与幼果；群体反复出现时对幼果期影响明显。',
    traits: '脸颊有明显黑斑，体型小巧，常成群在果园内跳跃活动。',
    hours: '昼间，近人活动，晨昏集中。',
    advice: '检出即告警；群体性强，驱离后建议回看画面确认清空。',
  },
  {
    name: '黑领椋鸟', en: 'Black-collared Starling', level: 'high',
    desc: '杂食成群，在果园啄食成熟果实',
    harm: '杂食性，成群在果园啄食成熟果实，常在短时间内集中取食。',
    traits: '头部乳白色，颈侧具黑色宽环带，飞行时翼下白斑醒目。',
    hours: '昼间，常小群活动。',
    advice: '检出即告警；与丝光椋鸟混群出现时建议一并驱离。',
  },
  {
    name: '丝光椋鸟', en: 'Red-billed Starling', level: 'high',
    desc: '集群啄果，常与黑领椋鸟混群',
    harm: '集群啄食成熟果实，常与黑领椋鸟混群出现，危害叠加。',
    traits: '翼羽带丝光般的蓝灰色光泽，喙端橙红色。',
    hours: '昼间，集群往返果园。',
    advice: '检出即告警；混群出现时建议双模驱离。',
  },
  {
    name: '红嘴蓝鹊', en: 'Red-billed Blue Magpie', level: 'high',
    desc: '集群穿林活动，啄食果实',
    harm: '集群穿林活动，啄食果实，也会翻找树皮下的虫类，对挂果树干扰大。',
    traits: '长尾蓝灰色带白斑，红喙红腿，体态张扬易识别。',
    hours: '昼间，成群穿林。',
    advice: '检出即告警；集群个体对声波敏感，驱离效果好。',
  },
  {
    name: '东方喜鹊', en: 'Oriental Magpie', level: 'mid',
    desc: '会啄食果实，也捕食果园害虫',
    harm: '杂食性，会啄食果实，但同样捕食果园害虫，影响具两面性；建议结合实际情况判断。',
    traits: '黑白配色的长尾体态，肩腹白色明显。',
    hours: '昼间活动。',
    advice: '告警可人工判断后驱离或忽略。',
  },
  {
    name: '山斑鸠', en: 'Oriental Turtle Dove', level: 'mid',
    desc: '地面取食落粒草籽，偶上树啄果',
    harm: '多在地面取食落粒与草籽，偶上树啄食果实，整体危害有限。',
    traits: '体背灰褐带鳞状斑，颈侧具杂色斑块，起飞时拍翅声明显。',
    hours: '昼间，多在地面活动。',
    advice: '告警可人工判断后驱离或忽略。',
  },
  {
    name: '珠颈斑鸠', en: 'Spotted Dove', level: 'mid',
    desc: '以地面种子为主食，危害有限',
    harm: '以地面种子与落粒为主食，在果园内危害有限。',
    traits: '颈侧具珍珠状斑点而得名，体色粉褐。',
    hours: '昼间，地面活动。',
    advice: '告警可人工判断后忽略。',
  },
  {
    name: '栗腹文鸟', en: 'Chestnut Munia', level: 'mid',
    desc: '以草籽为主食，基本不碰果实',
    harm: '以草籽为主食，对果实基本无影响。',
    traits: '头部与腹部栗褐色，常成小群在草丛活动。',
    hours: '昼间，草丛活动。',
    advice: '建议忽略其告警。',
  },
  {
    name: '花蜜鸟', en: 'Garden Sunbird', level: 'low',
    desc: '食花蜜为主，兼助传粉',
    harm: '以花蜜为主食，基本不损害果实，兼有帮助传粉的作用。',
    traits: '体型极小，喙细长下弯，雄鸟常带金属光泽羽色。',
    hours: '昼间，花丛活动。',
    advice: '建议忽略其告警。',
  },
  {
    name: '白领翡翠', en: 'Collared Kingfisher', level: 'low',
    desc: '主食鱼虾，果园多为路过误入',
    harm: '主食鱼虾等水生动物，出现在果园多为路过误入，无果实危害。',
    traits: '上体蓝绿色，颈部有白色领环，常停在突出枝头。',
    hours: '昼间，喜近水域。',
    advice: '建议忽略其告警。',
  },
]
