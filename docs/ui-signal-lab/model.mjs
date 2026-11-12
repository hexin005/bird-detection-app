export const concepts = [
 {id:'notice',name:'公共告示',no:'01',tag:'推荐 · 一眼找到待办',desc:'公告栏式主次：告警先看证据，控制先选动作，记录按日期归档。'},
 {id:'dossier',name:'值班案卷',no:'02',tag:'纸本档案 · 叙事感',desc:'把一次鸟情变成一份案卷：照片、核对、执行回执依次展开。'},
 {id:'dispatch',name:'调度台',no:'03',tag:'暗色仪表 · 高效操作',desc:'以值班席为中心：紧凑队列、明确设备状态、连续事件日志。'},
 {id:'field',name:'现场手册',no:'04',tag:'大字号 · 手机优先',desc:'每次只处理一个决定：先看鸟，再选设备，最后查回执。'}
];
export const initialAlarms = () => [
 {id:'SG-014',species:'珠颈斑鸠',count:1,confidence:93,time:'09:42',date:'11月09日',image:'assets/dove.jpg',status:'new',position:'东区 · 01 号监控点'},
 {id:'SG-013',species:'白喉红臀鹎',count:2,confidence:94,time:'09:38',date:'11月09日',image:'assets/bulbul.jpg',status:'new',position:'东区 · 01 号监控点'},
 {id:'SG-012',species:'珠颈斑鸠',count:1,confidence:91,time:'09:26',date:'11月09日',image:'assets/dove.jpg',status:'new',position:'东区 · 01 号监控点'},
 {id:'SG-011',species:'白喉红臀鹎',count:1,confidence:90,time:'08:51',date:'11月09日',image:'assets/bulbul.jpg',status:'handled',position:'东区 · 01 号监控点'}
];
export const modes = {both:'双模联动',acoustic:'声波',infrared:'红外'};
export function filteredAlarms(items,status,species){return items.filter(a=>(status==='all'||a.status===status)&&(!species||a.species===species));}
export function validCommand(mode,duration,online,busy){return Object.hasOwn(modes,mode)&&[3,5,8].includes(duration)&&online&&!busy;}
export const archives = [
 {id:'V-09A',title:'东区晨间巡护',date:'11月09日',time:'09:40',duration:'00:30',species:['珠颈斑鸠'],image:'assets/dove.jpg'},
 {id:'V-09B',title:'果树区鸟情观察',date:'11月09日',time:'09:12',duration:'01:24',species:['白喉红臀鹎'],image:'assets/bulbul.jpg'},
 {id:'V-08A',title:'傍晚例行巡护',date:'11月08日',time:'16:30',duration:'00:45',species:['珠颈斑鸠','白喉红臀鹎'],image:'assets/dove.jpg'}
];
