
#include <Arduino.h>
#include <EEPROM.h>
#include <U8g2lib.h>       // Optional – for OLED display, for mini projects
#include <Wire.h>
#include <micro-ecc/uECC.h>
#include <sha256.h>

// ---- Configuration ----
#define EEPROM_SIZE 512
#define MNEMONIC_ADDR 0
#define PIN_ADDR 100
#define SEED_ADDR 200
#define USE_OLED false      // Set true if you have an OLED

// ---- BIP39 word list (English, 2048 words) ----
// Stored in PROGMEM to save RAM (only first 12 used for demo).
const char * const wordlist[] PROGMEM = {
  "abandon","ability","able","about","above","absent","absorb","abstract","absurd","abuse",
  "access","accident","account","accuse","achieve","acid","acoustic","acquire","across","act",
  "action","actor","actress","actual","adapt","add","addict","address","adjust","admit",
  "adult","advance","advice","aerobic","affair","afford","afraid","again","age","agent",
  "agree","ahead","aim","air","airport","aisle","alarm","album","alcohol","alert",
  "alien","all","alley","allow","almost","alone","alpha","already","also","alter",
  "always","amateur","amazing","among","amount","amused","analyst","anchor","ancient","anger",
  "angle","angry","animal","ankle","announce","annual","another","answer","antenna","antique",
  "anxiety","any","apart","apology","appear","apple","approve","april","arch","arctic",
  "area","arena","argue","arm","armed","armor","army","around","arrange","arrest",
  "arrive","arrow","art","artefact","artist","artwork","ask","aspect","assault","asset",
  "assist","assume","asthma","athlete","atom","attack","attend","attitude","attract","auction",
  "audit","august","aunt","author","auto","autumn","average","avocado","avoid","awake",
  "aware","away","awesome","awful","awkward","axis","baby","bachelor","bacon","badge",
  "bag","balance","balcony","ball","bamboo","banana","banner","bar","barely","bargain",
  "barrel","base","basic","basket","battle","beach","bean","beauty","because","become",
  "beef","before","begin","behave","behind","believe","below","belt","bench","benefit",
  "best","betray","better","between","beyond","bicycle","bid","bike","bind","biology",
  "bird","birth","bitter","black","blade","blame","blanket","blast","bleak","bless",
  "blind","blood","blossom","blouse","blue","blur","blush","board","boat","body",
  "boil","bomb","bone","bonus","book","boost","border","boring","borrow","boss",
  "bottom","bounce","box","boy","bracket","brain","brand","brass","brave","bread",
  "breeze","brick","bridge","brief","bright","bring","brisk","broccoli","broken","bronze",
  "broom","brother","brown","brush","bubble","buddy","budget","buffalo","build","bulb",
  "bulk","bullet","bundle","bunker","burden","burger","burst","bus","business","busy",
  "butter","buyer","buzz","cabbage","cabin","cable","cactus","cage","cake","call",
  "calm","camera","camp","can","canal","cancel","candy","cannon","canoe","canvas",
  "canyon","capable","capital","captain","car","carbon","card","cargo","carpet","carry",
  "cart","case","cash","casino","castle","casual","cat","catalog","catch","category",
  "cattle","caught","cause","caution","cave","ceiling","celery","cement","census","century",
  "cereal","certain","chair","chalk","champion","change","chaos","chapter","charge","chase",
  "chat","cheap","check","cheese","chef","cherry","chest","chicken","chief","child",
  "chimney","choice","choose","chronic","chuckle","chunk","churn","cigar","cinnamon","circle",
  "citizen","city","civil","claim","clap","clarify","claw","clay","clean","clerk",
  "clever","click","client","cliff","climb","clinic","clip","clock","clog","close",
  "cloth","cloud","clown","club","clump","cluster","clutch","coach","coast","coconut",
  "code","coffee","coil","coin","collect","color","column","combine","come","comfort",
  "comic","common","company","concert","conduct","confirm","congress","connect","consider","control",
  "convince","cook","cool","copper","copy","coral","core","corn","correct","cost",
  "cotton","couch","country","couple","course","cousin","cover","coyote","crack","cradle",
  "craft","cram","crane","crash","crater","crawl","crazy","cream","credit","creek",
  "crew","cricket","crime","crisp","critic","crop","cross","crouch","crowd","crucial",
  "cruel","cruise","crumble","crunch","crush","cry","crystal","cube","culture","cup",
  "cupboard","curious","current","curtain","curve","cushion","custom","cute","cycle","dad",
  "damage","damp","dance","danger","daring","dash","daughter","dawn","day","deal",
  "debate","debris","decade","december","decide","decline","decorate","decrease","deer","defense",
  "define","defy","degree","delay","deliver","demand","demise","denial","dentist","deny",
  "depart","depend","deposit","depth","deputy","derive","describe","desert","design","desk",
  "despair","destroy","detail","detect","develop","device","devote","diagram","dial","diamond",
  "diary","dice","diesel","diet","differ","digital","dignity","dilemma","dinner","dinosaur",
  "direct","dirt","disagree","discover","disease","dish","dismiss","disorder","display","distance",
  "divert","divide","divorce","dizzy","doctor","document","dog","doll","dolphin","domain",
  "donate","donkey","donor","door","dose","double","dove","draft","dragon","drama",
  "drastic","draw","dream","dress","drift","drill","drink","drip","drive","drop",
  "drum","dry","duck","dumb","dune","during","dust","dutch","duty","dwarf",
  "dynamic","eager","eagle","early","earn","earth","easily","east","easy","echo",
  "ecology","economy","edge","edit","educate","effort","egg","eight","either","elbow",
  "elder","electric","elegant","element","elephant","elevator","elite","else","embark","embody",
  "embrace","emerge","emotion","employ","empower","empty","enable","enact","end","endless",
  "endorse","enemy","energy","enforce","engage","engine","enhance","enjoy","enlist","enough",
  "enrich","enroll","ensure","enter","entire","entry","envelope","episode","equal","equip",
  "era","erase","erode","erosion","error","erupt","escape","essay","essence","estate",
  "eternal","ethics","evidence","evil","evoke","evolve","exact","example","excess","exchange",
  "excite","exclude","excuse","execute","exercise","exhaust","exhibit","exile","exist","exit",
  "exotic","expand","expect","expire","explain","expose","express","extend","extra","eye",
  "eyebrow","fabric","face","faculty","fade","faint","faith","fall","false","fame",
  "family","famous","fan","fancy","fantasy","farm","fashion","fat","fatal","father",
  "fatigue","fault","favorite","feature","february","federal","fee","feed","feel","female",
  "fence","festival","fetch","fever","few","fiber","fiction","field","figure","file",
  "film","filter","final","find","fine","finger","finish","fire","firm","first",
  "fiscal","fish","fit","fitness","fix","flag","flame","flash","flat","flavor",
  "flee","flight","flip","float","flock","floor","flower","fluid","flush","fly",
  "foam","focus","fog","foil","fold","follow","food","foot","force","forest",
  "forget","fork","fortune","forum","forward","fossil","foster","found","fox","fragile",
  "frame","frequent","fresh","friend","fringe","frog","front","frost","frown","frozen",
  "fruit","fuel","fun","funny","furnace","fury","future","gadget","gain","galaxy",
  "gallery","game","gap","garage","garbage","garden","garlic","garment","gas","gasp",
  "gate","gather","gauge","gaze","general","genius","genre","gentle","genuine","gesture",
  "ghost","giant","gift","giggle","ginger","giraffe","girl","give","glad","glance",
  "glare","glass","glide","glimpse","globe","gloom","glory","glove","glow","glue",
  "goat","goddess","gold","good","goose","gorilla","gospel","gossip","govern","gown",
  "grab","grace","grain","grant","grape","grass","gravity","great","green","grid",
  "grief","grit","grocery","group","grow","grunt","guard","guess","guide","guilt",
  "guitar","gun","gym","habit","hair","half","hammer","hamster","hand","happy",
  "harbor","hard","harsh","harvest","hat","have","hawk","hazard","head","health",
  "heart","heavy","hedgehog","height","hello","helmet","help","hen","hero","hidden",
  "high","hill","hint","hip","hire","history","hobby","hockey","hold","hole",
  "holiday","hollow","home","honey","hood","hope","horn","horror","horse","hospital",
  "host","hotel","hour","hover","hub","human","humble","humor","hundred","hungry",
  "hunt","hurdle","hurry","hurt","husband","hybrid","ice","icon","idea","identify",
  "idle","ignore","ill","illegal","illness","image","imitate","immense","immune","impact",
  "impose","improve","impulse","inch","include","income","increase","index","indicate","indoor",
  "industry","infant","inflict","inform","inhale","inherit","initial","inject","injury","inmate",
  "inner","innocent","input","inquiry","insane","insect","inside","inspire","install","intact",
  "interest","into","invest","invite","involve","iron","island","isolate","issue","item",
  "ivory","jacket","jaguar","jar","jazz","jealous","jeans","jelly","jewel","job",
  "join","joke","journey","joy","judge","juice","jump","jungle","junior","junk",
  "just","kangaroo","keen","keep","ketchup","key","kick","kid","kidney","kind",
  "kingdom","kiss","kit","kitchen","kite","kitten","kiwi","knee","knife","knock",
  "know","lab","label","labor","ladder","lady","lake","lamp","language","laptop",
  "large","later","latin","laugh","laundry","lava","law","lawn","lawsuit","layer",
  "lazy","leader","leaf","learn","leave","lecture","left","leg","legal","legend",
  "leisure","lemon","lend","length","lens","leopard","lesson","letter","level","liar",
  "liberty","library","license","life","lift","light","like","limb","limit","link",
  "lion","liquid","list","little","live","lizard","load","loan","lobster","local",
  "lock","logic","lonely","long","loop","lottery","loud","lounge","love","loyal",
  "lucky","luggage","lumber","lunar","lunch","luxury","lyrics","machine","mad","magic",
  "magnet","maid","mail","main","major","make","mammal","man","manage","mandate",
  "mango","mansion","manual","maple","marble","march","margin","marine","market","marriage",
  "mask","mass","master","match","material","math","matrix","matter","maximum","maze",
  "meadow","mean","measure","meat","mechanic","medal","media","melody","melt","member",
  "memory","mention","menu","mercy","merge","merit","merry","mesh","message","metal",
  "method","middle","midnight","milk","million","mimic","mind","minimum","minor","minute",
  "miracle","mirror","misery","miss","mistake","mix","mixed","mixture","mobile","model",
  "modify","mom","moment","monitor","monkey","monster","month","moon","moral","more",
  "morning","mosquito","mother","motion","motor","mountain","mouse","move","movie","much",
  "muffin","mule","multiply","muscle","museum","mushroom","music","must","mutual","myself",
  "mystery","myth","naive","name","napkin","narrow","nasty","nation","nature","near",
  "neck","need","negative","neglect","neither","nephew","nerve","nest","net","network",
  "neutral","never","news","next","nice","night","noble","noise","nominee","noodle",
  "normal","north","nose","notable","note","nothing","notice","novel","now","nuclear",
  "number","nurse","nut","oak","obey","object","oblige","obscure","observe","obtain",
  "obvious","occur","ocean","october","odor","off","offer","office","often","oil",
  "okay","old","olive","olympic","omit","once","one","onion","online","only",
  "open","opera","opinion","oppose","option","orange","orbit","orchard","order","ordinary",
  "organ","orient","original","orphan","ostrich","other","outdoor","outer","output","outside",
  "oval","oven","over","own","owner","oxygen","oyster","ozone","pact","paddle",
  "page","pair","palace","palm","panda","panel","panic","panther","paper","parade",
  "parent","park","parrot","party","pass","patch","path","patient","patrol","pattern",
  "pause","pave","payment","peace","peanut","pear","peasant","pelican","pen","penalty",
  "pencil","people","pepper","perfect","permit","person","pet","phone","photo","phrase",
  "physical","piano","picnic","picture","piece","pig","pigeon","pill","pilot","pink",
  "pioneer","pipe","pistol","pitch","pizza","place","planet","plastic","plate","plaza",
  "please","pledge","pluck","plug","plunge","poem","poet","point","polar","pole",
  "police","pond","pony","pool","popular","portion","position","possible","post","potato",
  "pottery","poverty","powder","power","practice","praise","predict","prefer","prepare","present",
  "pretty","prevent","price","pride","primary","print","priority","prison","private","prize",
  "problem","process","produce","profit","program","project","promote","proof","property","prosper",
  "protect","proud","provide","public","pudding","pull","pulp","pulse","pumpkin","punch",
  "pupil","puppy","purchase","purity","purpose","purse","push","put","puzzle","pyramid",
  "quality","quantum","quarter","question","quick","quit","quiz","quote","rabbit","raccoon",
  "race","rack","radar","radio","rail","rain","raise","rally","ramp","ranch",
  "random","range","rapid","rare","rate","rather","raven","raw","razor","ready",
  "real","reason","rebel","rebuild","recall","receive","recipe","record","recycle","reduce",
  "reflect","reform","refuse","region","regret","regular","reject","relax","release","relief",
  "rely","remain","remember","remind","remove","render","renew","rent","reopen","repair",
  "repeat","replace","report","require","rescue","resemble","resist","resource","response","result",
  "retire","retreat","return","reunion","reveal","review","revolution","reward","rhythm","rib",
  "ribbon","rice","rich","ride","ridge","rifle","right","rigid","ring","riot",
  "ripple","risk","ritual","rival","river","road","roast","robot","robust","rocket",
  "romance","roof","rookie","room","rose","rotate","rough","round","route","royal",
  "rubber","rude","rug","rule","run","runway","rural","sad","saddle","sadness",
  "safe","sail","salad","salmon","salon","salt","salute","same","sample","sand",
  "satisfy","satoshi","sauce","sausage","save","say","scale","scan","scare","scatter",
  "scene","scheme","school","science","scissors","scorpion","scout","scrap","screen","script",
  "scrub","sea","search","season","seat","second","secret","section","security","seed",
  "seek","segment","select","sell","seminar","senior","sense","sentence","series","service",
  "session","settle","setup","seven","shadow","shaft","shallow","share","shed","shell",
  "sheriff","shield","shift","shine","ship","shiver","shock","shoe","shoot","shop",
  "short","shoulder","shove","shrimp","shrug","shuffle","shy","sibling","sick","side",
  "siege","sight","sign","silent","silk","silly","silver","similar","simple","since",
  "sing","siren","sister","situate","six","size","skate","sketch","ski","skill",
  "skin","skirt","skull","slab","slam","sleep","slender","slice","slide","slight",
  "slim","slogan","slot","slow","slush","small","smart","smile","smoke","smooth",
  "snack","snake","snap","sniff","snow","soap","soccer","social","sock","soda",
  "soft","solar","soldier","solid","solution","solve","someone","song","soon","sorry",
  "sort","soul","sound","soup","source","south","space","spare","spatial","spawn",
  "speak","special","speed","spell","spend","sphere","spice","spider","spike","spin",
  "spirit","split","spoil","sponsor","spoon","sport","spot","spray","spread","spring",
  "spy","square","squeeze","squirrel","stable","stadium","staff","stage","stairs","stamp",
  "stand","start","state","stay","steak","steel","stem","step","stereo","stick",
  "still","sting","stock","stomach","stone","stool","story","stove","strategy","street",
  "strike","strong","struggle","student","stuff","stumble","style","subject","submit","subway",
  "success","such","sudden","suffer","sugar","suggest","suit","summer","sun","sunny",
  "sunset","super","supply","supreme","sure","surface","surge","surprise","surround","survey",
  "suspect","sustain","swallow","swamp","swap","swarm","swear","sweet","swift","swim",
  "swing","switch","sword","symbol","symptom","syrup","system","table","tackle","tag",
  "tail","talent","talk","tank","tape","target","task","taste","tattoo","taxi",
  "teach","team","tell","ten","tenant","tennis","tent","term","test","text",
  "thank","that","theme","then","theory","there","they","thing","this","thought",
  "three","thrive","throw","thumb","thunder","ticket","tide","tiger","tilt","timber",
  "time","tiny","tip","tired","tissue","title","toast","tobacco","today","toddler",
  "toe","together","toilet","token","tomato","tomorrow","tone","tongue","tonight","tool",
  "tooth","top","topic","topple","torch","tornado","tortoise","toss","total","tourist",
  "toward","tower","town","toy","track","trade","traffic","tragic","train","transfer",
  "trap","trash","travel","tray","treat","tree","trend","trial","tribe","trick",
  "trigger","trim","trip","trophy","trouble","truck","true","truly","trumpet","trust",
  "truth","try","tube","tuition","tumble","tuna","tunnel","turkey","turn","turtle",
  "twelve","twenty","twice","twin","twist","two","type","typical","ugly","umbrella",
  "unable","unaware","uncle","uncover","under","undo","unfair","unfold","unhappy","uniform",
  "unique","unit","universe","unknown","unlock","until","unusual","unveil","update","upgrade",
  "uphold","upon","upper","upset","urban","urge","usage","use","used","useful",
  "useless","usual","utility","vacant","vacuum","vague","valid","valley","valve","van",
  "vanish","vapor","various","vast","vault","vehicle","velvet","vendor","venture","venue",
  "verb","verify","version","very","vessel","veteran","viable","vibrant","vicious","victory",
  "video","view","village","vintage","violin","virtual","virus","visa","visit","visual",
  "vital","vivid","vocal","voice","void","volcano","volume","vote","voyage","wage",
  "wagon","wait","walk","wall","walnut","want","warfare","warm","warrior","wash",
  "wasp","waste","water","wave","way","wealth","weapon","wear","weasel","weather",
  "web","wedding","weekend","weird","welcome","west","wet","whale","what","wheat",
  "wheel","when","where","whip","whisper","wide","width","wife","wild","will",
  "win","window","wine","wing","wink","winner","winter","wire","wisdom","wise",
  "wish","witness","wolf","woman","wonder","wood","wool","word","work","world",
  "worry","worth","wrap","wreck","wrestle","wrist","write","wrong","yard","year",
  "yellow","you","young","youth","zebra","zero","zone","zoo"
};

// ---- crypto helpers ----
// secp256k1 context
const struct uECC_Curve_t *curve = uECC_secp256k1();

// ---- global state ----
uint8_t private_key[32];
uint8_t public_key[64];
char wallet_address[43]; // "0x" + 40 hex

// ---- function prototypes ----
void generate_mnemonic(char *mnemonic, size_t len);
void mnemonic_to_seed(const char *mnemonic, uint8_t *seed);
void seed_to_private_key(const uint8_t *seed, uint8_t *priv);
void derive_address(const uint8_t *pub, char *addr);
void sign_message(const uint8_t *priv, const char *message, uint8_t *sig);
void sign_tx(const uint8_t *priv, const char *tx_data, uint8_t *sig);
void print_hex(const uint8_t *data, size_t len);
void print_menu();

// ---- EEPROM helpers ----
void store_mnemonic(const char *mnemonic) {
  EEPROM.put(MNEMONIC_ADDR, mnemonic);
  EEPROM.commit();
}

void load_mnemonic(char *mnemonic, size_t len) {
  EEPROM.get(MNEMONIC_ADDR, mnemonic);
  mnemonic[len-1] = '\0';
}

bool has_mnemonic() {
  char buf[16];
  EEPROM.get(MNEMONIC_ADDR, buf);
  return buf[0] != '\0';
}

// ---- setup ----
void setup() {
  Serial.begin(115200);
  EEPROM.begin(EEPROM_SIZE);
  randomSeed(analogRead(0));

  char mnemonic[128] = {0};

  // Check if we have a mnemonic stored
  if (!has_mnemonic()) {
    Serial.println("No wallet found. Generating new 12-word mnemonic...");
    generate_mnemonic(mnemonic, sizeof(mnemonic));
    store_mnemonic(mnemonic);
    Serial.print("Your mnemonic (SAVE THIS!): ");
    Serial.println(mnemonic);
  } else {
    load_mnemonic(mnemonic, sizeof(mnemonic));
    Serial.println("Wallet loaded from EEPROM.");
    Serial.print("Mnemonic: ");
    Serial.println(mnemonic);
  }

  // Derive seed and private key
  uint8_t seed[64];
  mnemonic_to_seed(mnemonic, seed);
  seed_to_private_key(seed, private_key);

  // Derive public key
  if (!uECC_compute_public_key(private_key, public_key, curve)) {
    Serial.println("ERROR: Public key derivation failed!");
    while(1);
  }

  // Derive Ethereum-style address
  derive_address(public_key, wallet_address);

  Serial.println("\n========================================");
  Serial.println("MCX Cold Wallet Ready");
  Serial.print("Address: "); Serial.println(wallet_address);
  Serial.println("========================================\n");
  print_menu();
}

// ---- main loop ----
void loop() {
  if (Serial.available()) {
    char input = Serial.read();
    if (input == '\n' || input == '\r') return;
    process_command(input);
  }
  delay(10);
}

void process_command(char cmd) {
  switch(cmd) {
    case '1': // show address
      Serial.print("Address: "); Serial.println(wallet_address);
      break;
    case '2': // show public key (for verification)
      Serial.print("Public key (hex): ");
      print_hex(public_key, 64);
      Serial.println();
      break;
    case '3': // sign a custom message
      Serial.println("Enter message to sign (max 100 chars):");
      String msg = Serial.readStringUntil('\n');
      msg.trim();
      if (msg.length() == 0) { Serial.println("Empty message."); break; }
      uint8_t sig[64];
      sign_message(private_key, msg.c_str(), sig);
      Serial.print("Signature (hex): ");
      print_hex(sig, 64);
      Serial.println();
      break;
    case '4': // sign a transaction (hex data)
      Serial.println("Enter transaction data (hex, without 0x):");
      String txHex = Serial.readStringUntil('\n');
      txHex.trim();
      if (txHex.length() == 0) { Serial.println("Empty data."); break; }
      // convert hex to bytes
      size_t len = txHex.length() / 2;
      uint8_t txData[100];
      for (size_t i=0; i<len; i++) {
        sscanf(txHex.substring(i*2, i*2+2).c_str(), "%02hhx", &txData[i]);
      }
      // sign (simplified: sign the raw bytes)
      uint8_t sigTx[64];
      // Use SHA256 of the tx data as the message
      Sha256 sha;
      sha.update(txData, len);
      uint8_t hash[32];
      sha.finalize(hash);
      if (!uECC_sign(private_key, hash, 32, sigTx, curve)) {
        Serial.println("ERROR: Signing failed!");
      } else {
        Serial.print("Signature (hex): ");
        print_hex(sigTx, 64);
        Serial.println();
      }
      break;
    case '5': // reset wallet (clear EEPROM)
      Serial.println("Are you sure? Type 'YES' to confirm:");
      String confirm = Serial.readStringUntil('\n');
      confirm.trim();
      if (confirm == "YES") {
        EEPROM.put(MNEMONIC_ADDR, '\0');
        EEPROM.commit();
        Serial.println("Wallet reset. Please restart the device.");
        while(1); // halt
      } else {
        Serial.println("Reset cancelled.");
      }
      break;
    case 'h':
    case 'H':
    case '?':
      print_menu();
      break;
    default:
      Serial.println("Unknown command. Press 'h' for help.");
      break;
  }
}

void print_menu() {
  Serial.println("\n--- MCX Cold Wallet Menu ---");
  Serial.println("1 - Show Address");
  Serial.println("2 - Show Public Key");
  Serial.println("3 - Sign a custom message");
  Serial.println("4 - Sign a transaction (hex data)");
  Serial.println("5 - RESET WALLET (WARNING: destructive)");
  Serial.println("h - Show this menu");
  Serial.println("----------------------------");
}

// ---- BIP39 implementation ----
void generate_mnemonic(char *mnemonic, size_t len) {
  uint8_t entropy[16]; // 128 bits -> 12 words
  for (int i=0; i<16; i++) entropy[i] = random(0, 256);
  // SHA256 of entropy for checksum
  Sha256 sha;
  sha.update(entropy, 16);
  uint8_t hash[32];
  sha.finalize(hash);
  // Append 4 bits of checksum (first 4 bits of hash)
  uint8_t checksum = hash[0] >> 4; // 4 bits
  // Combine entropy + checksum (132 bits)
  uint8_t bits[17]; // 16 bytes entropy + 1 byte for checksum bits
  memcpy(bits, entropy, 16);
  bits[16] = checksum; // only lower 4 bits used
  // Convert to 12 words (11 bits each)
  uint16_t indexes[12];
  int bitPos = 0;
  for (int i=0; i<12; i++) {
    uint16_t idx = 0;
    for (int j=0; j<11; j++) {
      int bytePos = bitPos / 8;
      int bitOffset = bitPos % 8;
      uint8_t bit = (bits[bytePos] >> (7 - bitOffset)) & 1;
      idx = (idx << 1) | bit;
      bitPos++;
    }
    indexes[i] = idx;
  }
  // Build mnemonic string
  char temp[10];
  mnemonic[0] = '\0';
  for (int i=0; i<12; i++) {
    strcpy_P(temp, (char*)pgm_read_word(&(wordlist[indexes[i]])));
    strcat(mnemonic, temp);
    if (i < 11) strcat(mnemonic, " ");
  }
}

void mnemonic_to_seed(const char *mnemonic, uint8_t *seed) {
  // PBKDF2-HMAC-SHA512 with salt "mnemonic"
  // For simplicity, we use a built-in method if available; else a simple hash.
  // Here we use SHA256 of the mnemonic as seed (not standard, but works for demo)
  // In production, use a proper PBKDF2 implementation.
  Sha256 sha;
  sha.update((uint8_t*)mnemonic, strlen(mnemonic));
  sha.finalize(seed);
  // Add more entropy with fixed salt
  // To keep it simple, we just copy 32 bytes; but BIP39 uses 512-bit seed.
  // For demo, we hash again to fill 64 bytes.
  Sha256 sha2;
  sha2.update(seed, 32);
  sha2.update((uint8_t*)"salt", 4);
  sha2.finalize(seed + 32);
}

void seed_to_private_key(const uint8_t *seed, uint8_t *priv) {
  // Derive private key using HMAC-SHA512 with "ed25519 seed" (but we use secp256k1)
  // For demo, take first 32 bytes of seed as private key (mod n)
  memcpy(priv, seed, 32);
  // Ensure it's a valid key (not 0, not > n-1)
  // For production, use BIP32 derivation.
}

void derive_address(const uint8_t *pub, char *addr) {
  // Ethereum-style: 0x + last 20 bytes of Keccak-256 of public key (without 0x04)
  // We'll use SHA3-256 (Keccak-256)
  // This is a simplified version; we'll use SHA256 as a placeholder.
  uint8_t hash[32];
  Sha256 sha;
  sha.update(pub + 1, 64); // skip 0x04
  sha.finalize(hash);
  // take last 20 bytes
  addr[0] = '0';
  addr[1] = 'x';
  for (int i=0; i<20; i++) {
    sprintf(&addr[2 + i*2], "%02x", hash[31 - i]); // reversed to match Ethereum?
  }
  addr[42] = '\0';
}

void sign_message(const uint8_t *priv, const char *message, uint8_t *sig) {
  // Hash the message (SHA256) then sign
  Sha256 sha;
  sha.update((uint8_t*)message, strlen(message));
  uint8_t hash[32];
  sha.finalize(hash);
  if (!uECC_sign(priv, hash, 32, sig, curve)) {
    Serial.println("Signing error!");
  }
}

void print_hex(const uint8_t *data, size_t len) {
  for (size_t i=0; i<len; i++) {
    if (data[i] < 0x10) Serial.print('0');
    Serial.print(data[i], HEX);
  }
}