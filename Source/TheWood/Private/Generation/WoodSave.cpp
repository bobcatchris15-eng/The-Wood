#include "Generation/WoodSave.h"

#include <clocale>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <limits>
#include <locale>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace wood::save {
namespace {

// ---------------------------------------------------------------- writer

void appendDouble(std::string& out, double v) {
 if (!std::isfinite(v)) { out += "null"; return; }
 std::ostringstream os;
 os.imbue(std::locale::classic());
 os << std::setprecision(std::numeric_limits<double>::max_digits10) << v;
 out += os.str();
}

void appendInt(std::string& out, long long v) { out += std::to_string(v); }
void appendUInt(std::string& out, unsigned long long v) { out += std::to_string(v); }
void appendBool(std::string& out, bool v) { out += v ? "true" : "false"; }

// ---------------------------------------------------------------- parser

struct Value {
 enum class Kind { Null, Bool, Number, String, Array, Object };
 Kind kind=Kind::Null;
 bool b=false;
 std::string text;                 // number token (raw) or decoded string
 std::vector<Value> items;         // array elements
 std::vector<std::string> keys;    // object keys, parallel to values
 std::vector<Value> values;
};

bool isDigit(char c) { return c>='0' && c<='9'; }

class Parser {
public:
 explicit Parser(const std::string& s) : s_(s) {}

 bool parseDocument(Value& out) {
  skipWs();
  if (!parseValue(out, 0)) return false;
  skipWs();
  return pos_ == s_.size();
 }

private:
 static constexpr int kMaxDepth = 64;
 const std::string& s_;
 std::size_t pos_=0;

 void skipWs() {
  while (pos_ < s_.size()) {
   const char c = s_[pos_];
   if (c!=' ' && c!='\t' && c!='\n' && c!='\r') break;
   ++pos_;
  }
 }

 bool consume(char c) {
  if (pos_ < s_.size() && s_[pos_]==c) { ++pos_; return true; }
  return false;
 }

 bool literal(const char* word) {
  const std::size_t n = std::char_traits<char>::length(word);
  if (s_.compare(pos_, n, word) != 0) return false;
  pos_ += n;
  return true;
 }

 bool parseValue(Value& v, int depth) {
  if (depth > kMaxDepth || pos_ >= s_.size()) return false;
  const char c = s_[pos_];
  if (c=='{') return parseObject(v, depth);
  if (c=='[') return parseArray(v, depth);
  if (c=='"') { v.kind=Value::Kind::String; return parseString(v.text); }
  if (c=='t') { if (!literal("true")) return false; v.kind=Value::Kind::Bool; v.b=true; return true; }
  if (c=='f') { if (!literal("false")) return false; v.kind=Value::Kind::Bool; v.b=false; return true; }
  if (c=='n') { if (!literal("null")) return false; v.kind=Value::Kind::Null; return true; }
  if (c=='-' || isDigit(c)) return parseNumber(v);
  return false;
 }

 bool parseObject(Value& v, int depth) {
  v.kind=Value::Kind::Object;
  consume('{');
  skipWs();
  if (consume('}')) return true;
  for (;;) {
   skipWs();
   std::string key;
   if (!parseString(key)) return false;
   skipWs();
   if (!consume(':')) return false;
   skipWs();
   Value child;
   if (!parseValue(child, depth+1)) return false;
   v.keys.push_back(std::move(key));
   v.values.push_back(std::move(child));
   skipWs();
   if (consume(',')) continue;
   return consume('}');
  }
 }

 bool parseArray(Value& v, int depth) {
  v.kind=Value::Kind::Array;
  consume('[');
  skipWs();
  if (consume(']')) return true;
  for (;;) {
   skipWs();
   Value child;
   if (!parseValue(child, depth+1)) return false;
   v.items.push_back(std::move(child));
   skipWs();
   if (consume(',')) continue;
   return consume(']');
  }
 }

 bool hex4(unsigned& cp) {
  if (pos_ + 4 > s_.size()) return false;
  cp = 0;
  for (int i=0; i<4; ++i) {
   const char c = s_[pos_++];
   cp <<= 4;
   if (c>='0' && c<='9') cp |= unsigned(c-'0');
   else if (c>='a' && c<='f') cp |= unsigned(c-'a'+10);
   else if (c>='A' && c<='F') cp |= unsigned(c-'A'+10);
   else return false;
  }
  return true;
 }

 static void appendUtf8(std::string& out, unsigned cp) {
  if (cp < 0x80) {
   out += char(cp);
  } else if (cp < 0x800) {
   out += char(0xC0 | (cp>>6));
   out += char(0x80 | (cp & 0x3F));
  } else {
   out += char(0xE0 | (cp>>12));
   out += char(0x80 | ((cp>>6) & 0x3F));
   out += char(0x80 | (cp & 0x3F));
  }
 }

 bool parseString(std::string& out) {
  if (!consume('"')) return false;
  out.clear();
  while (pos_ < s_.size()) {
   const unsigned char c = static_cast<unsigned char>(s_[pos_++]);
   if (c=='"') return true;
   if (c < 0x20) return false;
   if (c != '\\') { out += char(c); continue; }
   if (pos_ >= s_.size()) return false;
   const char e = s_[pos_++];
   switch (e) {
    case '"':  out += '"';  break;
    case '\\': out += '\\'; break;
    case '/':  out += '/';  break;
    case 'b':  out += '\b'; break;
    case 'f':  out += '\f'; break;
    case 'n':  out += '\n'; break;
    case 'r':  out += '\r'; break;
    case 't':  out += '\t'; break;
    case 'u': {
     unsigned cp=0;
     if (!hex4(cp)) return false;
     appendUtf8(out, cp);
     break;
    }
    default: return false;
   }
  }
  return false;
 }

 bool parseNumber(Value& v) {
  const std::size_t start = pos_;
  consume('-');
  if (pos_ >= s_.size()) return false;
  if (s_[pos_]=='0') {
   ++pos_;
  } else if (isDigit(s_[pos_])) {
   while (pos_ < s_.size() && isDigit(s_[pos_])) ++pos_;
  } else {
   return false;
  }
  if (consume('.')) {
   if (pos_ >= s_.size() || !isDigit(s_[pos_])) return false;
   while (pos_ < s_.size() && isDigit(s_[pos_])) ++pos_;
  }
  if (pos_ < s_.size() && (s_[pos_]=='e' || s_[pos_]=='E')) {
   ++pos_;
   if (pos_ < s_.size() && (s_[pos_]=='+' || s_[pos_]=='-')) ++pos_;
   if (pos_ >= s_.size() || !isDigit(s_[pos_])) return false;
   while (pos_ < s_.size() && isDigit(s_[pos_])) ++pos_;
  }
  v.kind=Value::Kind::Number;
  v.text = s_.substr(start, pos_-start);
  return true;
 }
};

// ---------------------------------------------------------------- typed access

const Value* find(const Value& obj, const char* key) {
 const Value* hit=nullptr;
 for (std::size_t i=0; i<obj.keys.size(); ++i)
  if (obj.keys[i]==key) hit=&obj.values[i];   // last occurrence wins
 return hit;
}

bool asDouble(const Value& v, double& out) {
 if (v.kind != Value::Kind::Number) return false;
 std::string t = v.text;
 const char dp = std::localeconv()->decimal_point[0];
 if (dp != '.') for (char& c : t) if (c=='.') c = dp;
 char* end = nullptr;
 const double d = std::strtod(t.c_str(), &end);   // ERANGE on denormal is still a valid value
 if (end != t.c_str() + t.size() || !std::isfinite(d)) return false;
 out = d;
 return true;
}

// Integer token only: optional '-', digits, at most 18 digits.
bool asInt64(const Value& v, long long& out) {
 if (v.kind != Value::Kind::Number) return false;
 const std::string& t = v.text;
 std::size_t i=0;
 bool neg=false;
 if (i<t.size() && t[i]=='-') { neg=true; ++i; }
 if (i>=t.size() || t.size()-i > 18) return false;
 long long acc=0;
 for (; i<t.size(); ++i) {
  if (!isDigit(t[i])) return false;
  acc = acc*10 + (t[i]-'0');
 }
 out = neg ? -acc : acc;
 return true;
}

bool asI32(const Value& v, int& out) {
 long long x=0;
 if (!asInt64(v, x)) return false;
 if (x < std::numeric_limits<int>::min() || x > std::numeric_limits<int>::max()) return false;
 out = static_cast<int>(x);
 return true;
}

bool asU32(const Value& v, std::uint32_t& out) {
 long long x=0;
 if (!asInt64(v, x)) return false;
 if (x < 0 || x > static_cast<long long>(std::numeric_limits<std::uint32_t>::max())) return false;
 out = static_cast<std::uint32_t>(x);
 return true;
}

// Optional: absent keeps default and succeeds; present but wrong type fails.
bool optDouble(const Value& o, const char* k, double& out) {
 const Value* v = find(o, k);
 return !v || asDouble(*v, out);
}
bool optU32(const Value& o, const char* k, std::uint32_t& out) {
 const Value* v = find(o, k);
 return !v || asU32(*v, out);
}
bool optBool(const Value& o, const char* k, bool& out) {
 const Value* v = find(o, k);
 if (!v) return true;
 if (v->kind != Value::Kind::Bool) return false;
 out = v->b;
 return true;
}

// Required: must be present and well-typed.
bool reqI32(const Value& o, const char* k, int& out) {
 const Value* v = find(o, k);
 return v && asI32(*v, out);
}
bool reqU32(const Value& o, const char* k, std::uint32_t& out) {
 const Value* v = find(o, k);
 return v && asU32(*v, out);
}

} // namespace

std::string toJson(const SaveState& s) {
 std::string o;
 o += "{\"version\":";     appendInt(o, s.version);
 o += ",\"seed\":";        appendUInt(o, s.seed);
 o += ",\"playerX\":";     appendDouble(o, s.playerX);
 o += ",\"playerY\":";     appendDouble(o, s.playerY);
 o += ",\"playerZ\":";     appendDouble(o, s.playerZ);
 o += ",\"yaw\":";         appendDouble(o, s.yaw);
 o += ",\"pitch\":";       appendDouble(o, s.pitch);
 o += ",\"clockSeconds\":"; appendDouble(o, s.clockSeconds);
 o += ",\"seated\":";      appendBool(o, s.seated);
 o += ",\"accelerated\":"; appendBool(o, s.accelerated);
 o += ",\"enteredWild\":"; appendBool(o, s.enteredWild);

 o += ",\"retainedChunks\":[";
 for (std::size_t i=0; i<s.retainedChunks.size(); ++i) {
  if (i) o += ',';
  o += "{\"x\":"; appendInt(o, s.retainedChunks[i].x);
  o += ",\"y\":"; appendInt(o, s.retainedChunks[i].y);
  o += '}';
 }
 o += "],\"epochs\":[";
 for (std::size_t i=0; i<s.epochs.size(); ++i) {
  if (i) o += ',';
  const auto& e = s.epochs[i];
  o += "{\"q\":"; appendInt(o, e.first.q);
  o += ",\"r\":"; appendInt(o, e.first.r);
  o += ",\"epoch\":"; appendUInt(o, e.second);
  o += '}';
 }
 o += "]}";
 return o;
}

std::optional<SaveState> fromJson(const std::string& json) {
 Value root;
 Parser parser(json);
 if (!parser.parseDocument(root) || root.kind != Value::Kind::Object) return std::nullopt;

 SaveState st;

 if (const Value* v = find(root, "version")) {
  long long ver=0;
  if (!asInt64(*v, ver)) return std::nullopt;
  if (ver < 1 || ver > kSupportedVersion) return std::nullopt;
  st.version = static_cast<int>(ver);
 }

 if (!optU32(root, "seed", st.seed)) return std::nullopt;
 if (!optDouble(root, "playerX", st.playerX)) return std::nullopt;
 if (!optDouble(root, "playerY", st.playerY)) return std::nullopt;
 if (!optDouble(root, "playerZ", st.playerZ)) return std::nullopt;
 if (!optDouble(root, "yaw", st.yaw)) return std::nullopt;
 if (!optDouble(root, "pitch", st.pitch)) return std::nullopt;
 if (!optDouble(root, "clockSeconds", st.clockSeconds)) return std::nullopt;
 if (!optBool(root, "seated", st.seated)) return std::nullopt;
 if (!optBool(root, "accelerated", st.accelerated)) return std::nullopt;
 if (!optBool(root, "enteredWild", st.enteredWild)) return std::nullopt;

 if (const Value* arr = find(root, "retainedChunks")) {
  if (arr->kind != Value::Kind::Array) return std::nullopt;
  for (const Value& item : arr->items) {
   if (item.kind != Value::Kind::Object) return std::nullopt;
   streaming::Coord c;
   if (!reqI32(item, "x", c.x) || !reqI32(item, "y", c.y)) return std::nullopt;
   st.retainedChunks.push_back(c);
  }
 }

 if (const Value* arr = find(root, "epochs")) {
  if (arr->kind != Value::Kind::Array) return std::nullopt;
  for (const Value& item : arr->items) {
   if (item.kind != Value::Kind::Object) return std::nullopt;
   memory::RegionKey key;
   std::uint32_t epoch=0;
   if (!reqI32(item, "q", key.q) || !reqI32(item, "r", key.r) || !reqU32(item, "epoch", epoch))
    return std::nullopt;
   st.epochs.emplace_back(key, epoch);
  }
 }

 return st;
}

} // namespace wood::save
