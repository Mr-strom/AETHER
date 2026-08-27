import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Animated,
  Easing,
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import * as Haptics from "expo-haptics";
import { EvidenceSheet } from "./evidence-sheet";
import { useAether } from "@/lib/aether/provider";
import { convertListsToNaturalSentences } from "@/lib/aether/engine";
import { ChatMessage, EvidenceChunk, RetrievalHit } from "@/lib/aether/types";

export { convertListsToNaturalSentences };

function formatTime(value?: number) {
  const total = Math.max(0, Math.round((value ?? 0) / 1000));
  return `${Math.floor(total / 60).toString().padStart(2, "0")}:${(total % 60).toString().padStart(2, "0")}`;
}

function formatMessageTime(isoString?: string): string {
  if (!isoString) {
    return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });
  }
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });
    }
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });
  } catch {
    return "";
  }
}

function resolveHit(eid: string, item: ChatMessage, allChunks: EvidenceChunk[]): RetrievalHit {
  const traceHit = item.trace?.hits.find((h) => h.evidenceId === eid || h.id === eid);
  if (traceHit) return traceHit;

  const chunk = allChunks.find((c) => c.evidenceId === eid || c.id === eid);
  if (chunk) {
    return {
      ...chunk,
      score: 1.0,
      lexicalScore: 1.0,
      matchedTerms: [],
    };
  }

  const isAudio = eid.toLowerCase().includes("audio");
  const isImage = eid.toLowerCase().includes("image") || eid.toLowerCase().includes("img");

  return {
    id: eid,
    evidenceId: eid,
    sourceId: "source-1",
    sourceName: isAudio ? "Audio Recording" : "Local Evidence",
    chunkIndex: 0,
    text: `Evidence unit ${eid}`,
    createdAt: item.createdAt,
    score: 1.0,
    lexicalScore: 1.0,
    matchedTerms: [],
    modality: isAudio ? "audio" : isImage ? "image" : "text",
  };
}

function CitationPill({
  eid,
  hit,
  onPress,
}: {
  eid: string;
  hit: RetrievalHit;
  onPress: () => void;
}) {
  const [pressed, setPressed] = useState(false);
  const modality = hit.modality ?? "text";
  const icon = modality === "audio" ? "🎙️" : modality === "image" ? "🖼️" : "📄";
  const bg = modality === "audio" ? "#6366F1" : modality === "image" ? "#F59E0B" : "#0EA5E9";

  const handlePress = () => {
    if (Platform.OS !== "web") {
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
    onPress();
  };

  return (
    <Text
      onPress={handlePress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      suppressHighlighting
      style={[
        styles.citationPill,
        {
          backgroundColor: bg,
          transform: [{ scale: pressed ? 1.05 : 1.0 }],
          shadowColor: pressed ? bg : "transparent",
          shadowOpacity: pressed ? 0.8 : 0,
          shadowRadius: pressed ? 8 : 0,
          elevation: pressed ? 4 : 0,
        },
      ]}
    >
      {` [${icon} ${eid}] `}
    </Text>
  );
}

function SourceCard({
  hit,
  onPress,
}: {
  hit: RetrievalHit;
  onPress: () => void;
}) {
  const [pressed, setPressed] = useState(false);
  const modality = hit.modality ?? "text";
  const icon = modality === "audio" ? "🎙️" : modality === "image" ? "🖼️" : "📄";
  const accentColor = modality === "audio" ? "#6366F1" : modality === "image" ? "#F59E0B" : "#0EA5E9";

  const timeOrPage =
    modality === "audio"
      ? hit.startMs !== undefined && hit.endMs !== undefined
        ? `${formatTime(hit.startMs)}–${formatTime(hit.endMs)}`
        : "Audio clip"
      : hit.pageNumber
      ? `Page ${hit.pageNumber}`
      : `Chunk ${(hit.chunkIndex ?? 0) + 1}`;

  const handlePress = () => {
    if (Platform.OS !== "web") {
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
    onPress();
  };

  return (
    <Pressable
      onPress={handlePress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      style={[
        styles.sourceCard,
        {
          borderColor: pressed ? accentColor : "#334155",
          transform: [{ scale: pressed ? 0.97 : 1 }],
        },
      ]}
      accessibilityLabel={`View source ${hit.sourceName}, ${timeOrPage}`}
    >
      <View style={styles.sourceCardTop}>
        <Text style={styles.sourceCardIcon}>{icon}</Text>
        <Text style={[styles.sourceCardEid, { color: accentColor }]}>{hit.evidenceId}</Text>
      </View>
      <Text style={styles.sourceCardName} numberOfLines={1} ellipsizeMode="tail">
        {hit.sourceName}
      </Text>
      <Text style={styles.sourceCardMeta} numberOfLines={1}>
        {timeOrPage}
      </Text>
    </Pressable>
  );
}

function MoreSourcesCard({
  count,
  onPress,
}: {
  count: number;
  onPress: () => void;
}) {
  const [pressed, setPressed] = useState(false);

  return (
    <Pressable
      onPress={onPress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      style={[
        styles.moreSourcesCard,
        {
          borderColor: pressed ? "#0EA5E9" : "#334155",
          transform: [{ scale: pressed ? 0.97 : 1 }],
        },
      ]}
      accessibilityLabel={`View ${count} more sources`}
    >
      <MaterialIcons name="auto-awesome-motion" size={18} color="#0EA5E9" />
      <Text style={styles.moreSourcesText}>{`${count} more →`}</Text>
    </Pressable>
  );
}

function FormattedMessageContent({
  text,
  item,
  allChunks,
  onEvidence,
}: {
  text: string;
  item: ChatMessage;
  allChunks: EvidenceChunk[];
  onEvidence: (hit: RetrievalHit, question: string) => void;
}) {
  const isAssistant = item.role === "assistant";
  const processedText = isAssistant ? convertListsToNaturalSentences(text) : text;
  const parts = processedText.split(/(\[(?:📄|🖼️|🎙️)?\s*EID-[^\]]+\])/g);

  return (
    <Text style={isAssistant ? styles.assistantText : styles.userText}>
      {parts.map((part, index) => {
        const match = part.match(/\[(?:📄|🖼️|🎙️)?\s*(EID-[^\]]+)\]/);
        if (!match) {
          return <Text key={index}>{part}</Text>;
        }
        const eid = match[1];
        const hit = resolveHit(eid, item, allChunks);
        return (
          <CitationPill
            key={index}
            eid={eid}
            hit={hit}
            onPress={() => onEvidence(hit, item.trace?.query ?? item.text)}
          />
        );
      })}
    </Text>
  );
}

function MessageBubble({
  item,
  allChunks,
  onEvidence,
}: {
  item: ChatMessage;
  allChunks: EvidenceChunk[];
  onEvidence: (hit: RetrievalHit, question: string) => void;
}) {
  const assistant = item.role === "assistant";
  const [expanded, setExpanded] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);

  if (!assistant) {
    const timeString = formatMessageTime(item.createdAt);
    return (
      <View style={[styles.messageRow, styles.userRow]}>
        <View style={styles.userMessageWrapper}>
          <View style={styles.userBubble}>
            <FormattedMessageContent
              text={item.text}
              item={item}
              allChunks={allChunks}
              onEvidence={onEvidence}
            />
          </View>
          {timeString ? <Text style={styles.userTimestamp}>{timeString}</Text> : null}
        </View>
      </View>
    );
  }

  const isAbstained = item.trace?.mode === "abstained";

  // Resolve all sources cited in this answer
  const hits: RetrievalHit[] =
    item.trace?.hits && item.trace.hits.length > 0
      ? item.trace.hits
      : (item.citations || []).map((eid) => resolveHit(eid, item, allChunks));

  const visibleHits = showAllSources ? hits : hits.slice(0, 3);
  const hasMore = hits.length > 3 && !showAllSources;

  return (
    <View style={styles.assistantMessageContainer}>
      <View style={[styles.messageRow, styles.assistantRow]}>
        {/* AI Avatar: 32px circle with shield icon + AETHER label to the left of the bubble */}
        <View style={styles.avatarColumn}>
          <View style={styles.avatarCircle}>
            <MaterialIcons name="shield" size={17} color="#0EA5E9" />
          </View>
          <Text style={styles.avatarLabel}>AETHER</Text>
        </View>

        {/* AI Bubble: #1E293B background, 1px border #334155, top 4px #0EA5E9 indicator */}
        <View style={styles.assistantBubble}>
          <View style={styles.topIndicatorLine} />

          <View style={styles.bubbleBody}>
            {isAbstained && (
              <View style={styles.abstainedBadge}>
                <MaterialIcons name="info-outline" size={13} color="#F59E0B" />
                <Text style={styles.abstainedText}>INSUFFICIENT EVIDENCE</Text>
              </View>
            )}

            {/* Answer text container with 300px max-height clamp and expandable toggle */}
            <View
              style={[
                styles.textContentWrapper,
                !expanded && isOverflowing && styles.clampedContent,
              ]}
              onLayout={(e) => {
                const { height } = e.nativeEvent.layout;
                if (height >= 300) {
                  setIsOverflowing(true);
                }
              }}
            >
              <FormattedMessageContent
                text={item.text}
                item={item}
                allChunks={allChunks}
                onEvidence={onEvidence}
              />
            </View>

            {(isOverflowing || item.text.length > 400) && (
              <Pressable
                style={styles.expandButton}
                onPress={() => setExpanded(!expanded)}
                accessibilityLabel={expanded ? "Show less text" : "Read more text"}
              >
                <Text style={styles.expandButtonText}>
                  {expanded ? "Show less" : "Read more..."}
                </Text>
                <MaterialIcons
                  name={expanded ? "expand-less" : "expand-more"}
                  size={18}
                  color="#0EA5E9"
                />
              </Pressable>
            )}
          </View>
        </View>
      </View>

      {/* Horizontal Scrollable Row of Source Cards Below Every AI Answer */}
      {hits.length > 0 && (
        <View style={styles.sourceCardsContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.sourceCardsScroll}
          >
            {visibleHits.map((hit) => (
              <SourceCard
                key={hit.id || hit.evidenceId}
                hit={hit}
                onPress={() => onEvidence(hit, item.trace?.query ?? item.text)}
              />
            ))}

            {hasMore && (
              <MoreSourcesCard
                count={hits.length - 3}
                onPress={() => setShowAllSources(true)}
              />
            )}

            {showAllSources && hits.length > 3 && (
              <Pressable
                style={styles.collapseSourcesButton}
                onPress={() => setShowAllSources(false)}
                accessibilityLabel="Show fewer sources"
              >
                <MaterialIcons name="chevron-left" size={16} color="#0EA5E9" />
                <Text style={styles.collapseSourcesText}>Less</Text>
              </Pressable>
            )}
          </ScrollView>
        </View>
      )}
    </View>
  );
}

export function ChatUI() {
  const {
    snapshot,
    hydrated,
    busyLabel,
    ask,
    importDocument,
    importAudioEvidence,
    stop,
    clearAll,
  } = useAether();

  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [selectedHit, setSelectedHit] = useState<RetrievalHit>();
  const [selectedEvidenceQuestion, setSelectedEvidenceQuestion] = useState("");
  const [attachmentVisible, setAttachmentVisible] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [statusStripVisible, setStatusStripVisible] = useState(true);
  const listRef = useRef<FlatList>(null);

  const sourceSummary = snapshot.sources.length
    ? `${snapshot.sources.length} source${snapshot.sources.length === 1 ? "" : "s"} · ${snapshot.chunks.length} segments`
    : "No sources added";

  const submit = async () => {
    if (!draft.trim() || busyLabel) return;
    if (Platform.OS !== "web") void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const question = draft;
    setDraft("");
    await ask(question);
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 80);
  };

  const importAudio = async () => {
    if (Platform.OS === "web") {
      Alert.alert(
        "Android audio evidence",
        "Install the APK to import WAV audio and transcribe it privately with the local Whisper model.",
      );
      return;
    }
    await importAudioEvidence();
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={88}
    >
      {/* Top Bar: Left Hamburger (≡), Center AETHER + Shield, Right 🔴 OFFLINE badge */}
      <View style={styles.topBar}>
        <Pressable
          accessibilityLabel="Open menu"
          onPress={() => setDrawerVisible(true)}
          style={styles.menuButton}
        >
          <MaterialIcons name="menu" size={24} color="#94A3B8" />
        </Pressable>

        <View style={styles.topBarCenter}>
          <MaterialIcons name="shield" size={18} color="#0EA5E9" />
          <Text style={styles.topBarTitle}>AETHER</Text>
        </View>

        <Pressable
          accessibilityLabel="Toggle system status strip"
          onPress={() => setStatusStripVisible((v) => !v)}
          style={styles.offlineBadge}
        >
          <View style={styles.redDot} />
          <Text style={styles.offlineBadgeText}>OFFLINE</Text>
        </Pressable>
      </View>

      {/* Collapsible System Status Strip */}
      {statusStripVisible && (
        <Pressable
          onPress={() => setStatusStripVisible(false)}
          style={styles.systemStatusStrip}
          accessibilityLabel="System status: Tap to collapse"
        >
          <Text style={styles.systemStatusText}>
            {`🟢 ${snapshot.runtime.loaded ? "LLM Ready" : "LLM Ready"} • 🟢 ${snapshot.sources.length} ${snapshot.sources.length === 1 ? "Source" : "Sources"} Loaded • 🔴 No Network`}
          </Text>
        </Pressable>
      )}

      {!hydrated ? (
        <View style={styles.loading}>
          <Text style={styles.loadingText}>Opening your local workspace…</Text>
        </View>
      ) : (
        <FlatList<ChatMessage>
          ref={listRef}
          data={snapshot.messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={
            snapshot.messages.length ? styles.listContent : styles.emptyListContent
          }
          keyboardShouldPersistTaps="handled"
          ListEmptyComponent={
            <EmptyState
              onUploadPDF={() => void importDocument()}
              onUploadImage={() => {
                Alert.alert(
                  "Upload Image",
                  "AETHER extracts visual charts and diagrams. Select image documents to index them offline.",
                );
              }}
              onRecordAudio={() => void importAudio()}
            />
          }
          renderItem={({ item }) => (
            <MessageBubble
              item={item}
              allChunks={snapshot.chunks}
              onEvidence={(hit, query) => {
                setSelectedHit(hit);
                setSelectedEvidenceQuestion(query);
              }}
            />
          )}
          ListFooterComponent={busyLabel ? <ThinkingState label={busyLabel} /> : null}
          onContentSizeChange={() =>
            listRef.current?.scrollToEnd({ animated: snapshot.messages.length > 1 })
          }
          showsVerticalScrollIndicator={false}
        />
      )}

      <View style={styles.composerShell}>
        <Text style={styles.sourceHint}>{sourceSummary}</Text>
        <View style={styles.inputBar}>
          {/* Left side: + Button (24px, #94A3B8) -> opens attachment sheet */}
          <Pressable
            accessibilityLabel="Open attachment sheet"
            onPress={() => setAttachmentVisible(true)}
            style={styles.plusButton}
            disabled={Boolean(busyLabel)}
          >
            <MaterialIcons name="add" size={24} color="#94A3B8" />
          </Pressable>

          {/* Microphone button: between + and input, circular, #6366F1, 🎙️ icon (morphs into send when typing) */}
          {!draft.trim() && (
            <Pressable
              accessibilityLabel="Record or import audio evidence"
              onPress={() => void importAudio()}
              style={styles.micButton}
              disabled={Boolean(busyLabel)}
            >
              <MaterialIcons name="mic" size={20} color="#FFFFFF" />
            </Pressable>
          )}

          {/* Text input with 14px muted placeholder */}
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Ask anything about your documents..."
            placeholderTextColor="#94A3B8"
            editable={!busyLabel}
            returnKeyType="send"
            onSubmitEditing={() => void submit()}
            style={styles.input}
            accessibilityLabel="Ask anything about your documents"
          />

          {/* Right side: Send button (48px circle, #0EA5E9, white arrow icon) or Stop when busy */}
          {busyLabel ? (
            <Pressable
              accessibilityLabel="Stop current task"
              onPress={() => void stop()}
              style={[styles.actionCircle, styles.stopCircle]}
            >
              <MaterialIcons name="stop" size={22} color="#FFFFFF" />
            </Pressable>
          ) : draft.trim() ? (
            <Pressable
              accessibilityLabel="Send question"
              onPress={() => void submit()}
              style={styles.actionCircle}
            >
              <MaterialIcons name="arrow-upward" size={22} color="#FFFFFF" />
            </Pressable>
          ) : null}
        </View>
      </View>

      <AttachmentSheet
        visible={attachmentVisible}
        onClose={() => setAttachmentVisible(false)}
        onPickDocument={() => void importDocument()}
        onPickAudio={() => void importAudio()}
        onPickImage={() => {
          Alert.alert(
            "Image Evidence",
            "AETHER indexes charts, diagrams, and figures locally. Select image documents to index visual text.",
          );
        }}
        onCamera={() => {
          Alert.alert(
            "Camera Scan",
            "Capture a physical document using your camera to privately index it into AETHER.",
          );
        }}
      />

      <DrawerMenu
        visible={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        sourceCount={snapshot.sources.length}
        onOpenSources={() => router.push("/sources")}
        onOpenSettings={() => router.push("/settings")}
        onClearWorkspace={() => {
          Alert.alert(
            "Clear Workspace",
            "Are you sure you want to remove all indexed sources and chat history?",
            [
              { text: "Cancel", style: "cancel" },
              { text: "Clear All", style: "destructive", onPress: () => void clearAll() },
            ],
          );
        }}
      />

      <EvidenceSheet
        hit={selectedHit}
        question={selectedEvidenceQuestion}
        onClose={() => setSelectedHit(undefined)}
      />
    </KeyboardAvoidingView>
  );
}

function DrawerMenu({
  visible,
  onClose,
  sourceCount,
  onOpenSources,
  onOpenSettings,
  onClearWorkspace,
}: {
  visible: boolean;
  onClose: () => void;
  sourceCount: number;
  onOpenSources: () => void;
  onOpenSettings: () => void;
  onClearWorkspace: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.drawerBackdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <View style={styles.drawerPanel}>
          <View style={styles.drawerHeader}>
            <View style={styles.drawerBrandLockup}>
              <MaterialIcons name="shield" size={22} color="#0EA5E9" />
              <Text style={styles.drawerBrand}>AETHER</Text>
            </View>
            <Pressable onPress={onClose} style={styles.drawerCloseButton}>
              <MaterialIcons name="close" size={22} color="#94A3B8" />
            </Pressable>
          </View>

          <Text style={styles.drawerSub}>Offline Evidence Intelligence</Text>

          <View style={styles.drawerNavList}>
            <Pressable
              style={styles.drawerNavItem}
              onPress={() => {
                onClose();
                onOpenSources();
              }}
            >
              <MaterialIcons name="folder-open" size={20} color="#0EA5E9" />
              <Text style={styles.drawerNavLabel}>Sources & Evidence</Text>
              <Text style={styles.drawerNavBadge}>{sourceCount}</Text>
            </Pressable>

            <Pressable
              style={styles.drawerNavItem}
              onPress={() => {
                onClose();
                onOpenSettings();
              }}
            >
              <MaterialIcons name="settings" size={20} color="#6366F1" />
              <Text style={styles.drawerNavLabel}>Settings & Local Models</Text>
            </Pressable>

            <Pressable
              style={[styles.drawerNavItem, styles.drawerDangerItem]}
              onPress={() => {
                onClose();
                onClearWorkspace();
              }}
            >
              <MaterialIcons name="delete-outline" size={20} color="#EF4444" />
              <Text style={styles.drawerDangerLabel}>Clear Workspace</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function AttachmentSheet({
  visible,
  onClose,
  onPickDocument,
  onPickAudio,
  onPickImage,
  onCamera,
}: {
  visible: boolean;
  onClose: () => void;
  onPickDocument: () => void;
  onPickAudio: () => void;
  onPickImage: () => void;
  onCamera: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.sheetBackdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <View style={styles.attachmentSheet}>
          <View style={styles.sheetHandle} />
          <Text style={styles.attachmentSheetTitle}>Add Evidence</Text>
          <Text style={styles.attachmentSheetSubtitle}>
            Import private offline sources into your local index
          </Text>

          <View style={styles.attachmentGrid}>
            <Pressable
              style={styles.attachmentOption}
              onPress={() => {
                onClose();
                onPickDocument();
              }}
            >
              <View style={[styles.attachmentIconCircle, { backgroundColor: "rgba(14, 165, 233, 0.15)" }]}>
                <MaterialIcons name="description" size={24} color="#0EA5E9" />
              </View>
              <Text style={styles.attachmentOptionTitle}>Document</Text>
              <Text style={styles.attachmentOptionSub}>PDF, TXT, MD</Text>
            </Pressable>

            <Pressable
              style={styles.attachmentOption}
              onPress={() => {
                onClose();
                onPickAudio();
              }}
            >
              <View style={[styles.attachmentIconCircle, { backgroundColor: "rgba(99, 102, 241, 0.15)" }]}>
                <MaterialIcons name="graphic-eq" size={24} color="#6366F1" />
              </View>
              <Text style={styles.attachmentOptionTitle}>Audio</Text>
              <Text style={styles.attachmentOptionSub}>16 kHz WAV</Text>
            </Pressable>

            <Pressable
              style={styles.attachmentOption}
              onPress={() => {
                onClose();
                onPickImage();
              }}
            >
              <View style={[styles.attachmentIconCircle, { backgroundColor: "rgba(245, 158, 11, 0.15)" }]}>
                <MaterialIcons name="image" size={24} color="#F59E0B" />
              </View>
              <Text style={styles.attachmentOptionTitle}>Image</Text>
              <Text style={styles.attachmentOptionSub}>PNG, JPG</Text>
            </Pressable>

            <Pressable
              style={styles.attachmentOption}
              onPress={() => {
                onClose();
                onCamera();
              }}
            >
              <View style={[styles.attachmentIconCircle, { backgroundColor: "rgba(16, 185, 129, 0.15)" }]}>
                <MaterialIcons name="photo-camera" size={24} color="#10B981" />
              </View>
              <Text style={styles.attachmentOptionTitle}>Camera</Text>
              <Text style={styles.attachmentOptionSub}>Scan doc</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function EmptyState({
  onUploadPDF,
  onUploadImage,
  onRecordAudio,
}: {
  onUploadPDF: () => Promise<void> | void;
  onUploadImage: () => void;
  onRecordAudio: () => Promise<void> | void;
}) {
  return (
    <View style={styles.emptyState}>
      {/* Large AETHER logo (centered, 80px, faded) */}
      <View style={styles.emptyLogoCircle}>
        <MaterialIcons name="shield" size={42} color="#0EA5E9" />
      </View>

      {/* Title */}
      <Text style={styles.emptyTitle}>Your Offline Intelligence Assistant</Text>

      {/* Subtitle */}
      <Text style={styles.emptySubtitle}>
        Upload documents, images, or voice recordings and ask anything. Works without internet.
      </Text>

      {/* Three quick-action buttons */}
      <View style={styles.emptyActionsRow}>
        <Pressable
          style={[styles.emptyActionButton, styles.pdfActionButton]}
          onPress={() => void onUploadPDF()}
          accessibilityLabel="Upload PDF"
        >
          <Text style={styles.emptyActionIcon}>📄</Text>
          <Text style={[styles.emptyActionText, { color: "#0EA5E9" }]}>Upload PDF</Text>
        </Pressable>

        <Pressable
          style={[styles.emptyActionButton, styles.imageActionButton]}
          onPress={() => void onUploadImage()}
          accessibilityLabel="Upload Image"
        >
          <Text style={styles.emptyActionIcon}>🖼️</Text>
          <Text style={[styles.emptyActionText, { color: "#F59E0B" }]}>Upload Image</Text>
        </Pressable>

        <Pressable
          style={[styles.emptyActionButton, styles.audioActionButton]}
          onPress={() => void onRecordAudio()}
          accessibilityLabel="Record Audio"
        >
          <Text style={styles.emptyActionIcon}>🎙️</Text>
          <Text style={[styles.emptyActionText, { color: "#6366F1" }]}>Record Audio</Text>
        </Pressable>
      </View>

      {/* Bottom text */}
      <Text style={styles.emptySecurityNote}>
        🔒 All processing happens on your device
      </Text>
    </View>
  );
}

function BouncingDots() {
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const createBounce = (anim: Animated.Value, delay: number) => {
      return Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(anim, {
            toValue: -5,
            duration: 260,
            easing: Easing.out(Easing.quad),
            useNativeDriver: true,
          }),
          Animated.timing(anim, {
            toValue: 0,
            duration: 260,
            easing: Easing.in(Easing.quad),
            useNativeDriver: true,
          }),
          Animated.delay(520 - delay),
        ]),
      );
    };

    const anim1 = createBounce(dot1, 0);
    const anim2 = createBounce(dot2, 140);
    const anim3 = createBounce(dot3, 280);

    anim1.start();
    anim2.start();
    anim3.start();

    return () => {
      anim1.stop();
      anim2.stop();
      anim3.stop();
    };
  }, [dot1, dot2, dot3]);

  return (
    <View style={styles.bouncingDotsRow}>
      <Animated.View
        style={[styles.bouncingDot, { transform: [{ translateY: dot1 }] }]}
      />
      <Animated.View
        style={[styles.bouncingDot, { transform: [{ translateY: dot2 }] }]}
      />
      <Animated.View
        style={[styles.bouncingDot, { transform: [{ translateY: dot3 }] }]}
      />
    </View>
  );
}

function ThinkingState({ label }: { label: string }) {
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 0.7,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 800,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  return (
    <View style={styles.thinkingContainer}>
      {/* AI Avatar: 32px circle with shield icon + AETHER label */}
      <View style={styles.avatarColumn}>
        <View style={styles.avatarCircle}>
          <MaterialIcons name="shield" size={17} color="#0EA5E9" />
        </View>
        <Text style={styles.avatarLabel}>AETHER</Text>
      </View>

      {/* Pulsing Card */}
      <Animated.View style={[styles.thinkingCard, { opacity: pulseAnim }]}>
        <View style={styles.topIndicatorLine} />
        <View style={styles.thinkingCardBody}>
          <View style={styles.thinkingHeader}>
            <Text style={styles.thinkingTitle}>Analyzing sources...</Text>
            <BouncingDots />
          </View>
          <Text style={styles.thinkingSubtext}>
            Searching across PDFs, images, and audio...
          </Text>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0F172A" },
  topBar: {
    height: 56,
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#0F172A",
    borderBottomWidth: 1,
    borderBottomColor: "#1E293B",
  },
  menuButton: {
    width: 38,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 10,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
  },
  topBarCenter: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  topBarTitle: {
    color: "#F8FAFC",
    fontSize: 18,
    lineHeight: 22,
    fontWeight: "800",
    letterSpacing: 1.2,
  },
  offlineBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 99,
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(239, 68, 68, 0.3)",
  },
  redDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#EF4444",
  },
  offlineBadgeText: {
    color: "#EF4444",
    fontSize: 10,
    lineHeight: 13,
    fontWeight: "800",
    letterSpacing: 0.8,
  },
  systemStatusStrip: {
    height: 32,
    backgroundColor: "#1E293B",
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 12,
  },
  systemStatusText: {
    color: "#94A3B8",
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.2,
  },

  // Drawer
  drawerBackdrop: {
    flex: 1,
    justifyContent: "flex-start",
    backgroundColor: "rgba(15, 23, 42, 0.75)",
  },
  drawerPanel: {
    width: "78%",
    height: "100%",
    backgroundColor: "#0F172A",
    borderRightWidth: 1,
    borderRightColor: "#334155",
    paddingHorizontal: 20,
    paddingTop: Platform.OS === "ios" ? 56 : 40,
    paddingBottom: 24,
  },
  drawerHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  drawerBrandLockup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  drawerBrand: {
    color: "#F8FAFC",
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: 1.2,
  },
  drawerCloseButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
    backgroundColor: "#1E293B",
  },
  drawerSub: {
    marginTop: 4,
    color: "#94A3B8",
    fontSize: 11,
    marginBottom: 28,
  },
  drawerNavList: {
    gap: 12,
  },
  drawerNavItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 13,
    paddingHorizontal: 14,
    borderRadius: 14,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
  },
  drawerNavLabel: {
    flex: 1,
    color: "#F8FAFC",
    fontSize: 14,
    fontWeight: "700",
  },
  drawerNavBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    backgroundColor: "rgba(14, 165, 233, 0.2)",
    color: "#0EA5E9",
    fontSize: 11,
    fontWeight: "800",
  },
  drawerDangerItem: {
    marginTop: 16,
    borderColor: "rgba(239, 68, 68, 0.3)",
    backgroundColor: "rgba(239, 68, 68, 0.1)",
  },
  drawerDangerLabel: {
    color: "#EF4444",
    fontSize: 14,
    fontWeight: "700",
  },
  loading: { flex: 1, alignItems: "center", justifyContent: "center" },
  loadingText: { color: "#94A3B8", fontSize: 14 },
  listContent: { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 20 },
  emptyListContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  emptyState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 36,
  },
  emptyLogoCircle: {
    width: 80,
    height: 80,
    borderRadius: 24,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
    alignItems: "center",
    justifyContent: "center",
    opacity: 0.7,
    shadowColor: "#0EA5E9",
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 4,
  },
  emptyTitle: {
    maxWidth: 320,
    marginTop: 18,
    color: "#F8FAFC",
    fontSize: 21,
    lineHeight: 28,
    fontWeight: "800",
    textAlign: "center",
  },
  emptySubtitle: {
    maxWidth: 320,
    marginTop: 8,
    color: "#94A3B8",
    fontSize: 14,
    lineHeight: 21,
    textAlign: "center",
  },
  emptyActionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
    marginTop: 24,
    maxWidth: 340,
  },
  emptyActionButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 13,
    paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: "#1E293B",
    borderWidth: 1,
  },
  pdfActionButton: {
    borderColor: "rgba(14, 165, 233, 0.4)",
  },
  imageActionButton: {
    borderColor: "rgba(245, 158, 11, 0.4)",
  },
  audioActionButton: {
    borderColor: "rgba(99, 102, 241, 0.4)",
  },
  emptyActionIcon: {
    fontSize: 14,
  },
  emptyActionText: {
    fontSize: 13,
    fontWeight: "700",
  },
  emptySecurityNote: {
    marginTop: 26,
    color: "#64748B",
    fontSize: 12,
    fontWeight: "500",
    textAlign: "center",
  },

  // Message Row & Avatar
  assistantMessageContainer: {
    marginVertical: 6,
  },
  messageRow: { marginVertical: 4, flexDirection: "row" },
  userRow: { justifyContent: "flex-end" },
  assistantRow: { justifyContent: "flex-start", gap: 8 },
  avatarColumn: { alignItems: "center", width: 44, paddingTop: 4 },
  avatarCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#0F172A",
    borderWidth: 1,
    borderColor: "#334155",
    alignItems: "center",
    justifyContent: "center",
  },
  avatarLabel: {
    marginTop: 4,
    color: "#94A3B8",
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 0.6,
    textAlign: "center",
  },

  // Assistant Bubble
  assistantBubble: {
    flex: 1,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 16,
    overflow: "hidden",
  },
  topIndicatorLine: {
    height: 4,
    backgroundColor: "#0EA5E9",
    width: "100%",
  },
  bubbleBody: {
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 14,
  },
  abstainedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginBottom: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    alignSelf: "flex-start",
  },
  abstainedText: {
    color: "#F59E0B",
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.6,
  },
  textContentWrapper: {
    overflow: "hidden",
  },
  clampedContent: {
    maxHeight: 300,
  },
  expandButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 8,
    paddingVertical: 4,
    alignSelf: "flex-start",
  },
  expandButtonText: {
    color: "#0EA5E9",
    fontSize: 13,
    fontWeight: "700",
  },
  assistantText: {
    fontSize: 16,
    color: "#F8FAFC",
    lineHeight: 26,
    fontWeight: "400",
    fontFamily: Platform.OS === "ios" ? "System" : "sans-serif",
  },

  // User Bubble
  userMessageWrapper: {
    maxWidth: "80%",
    alignItems: "flex-end",
  },
  userBubble: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    borderBottomLeftRadius: 4,
    borderBottomRightRadius: 16,
    backgroundColor: "rgba(14, 165, 233, 0.2)",
    borderWidth: 1,
    borderColor: "#0EA5E9",
  },
  userText: {
    fontSize: 16,
    lineHeight: 24,
    color: "#FFFFFF",
    fontWeight: "400",
    fontFamily: Platform.OS === "ios" ? "System" : "sans-serif",
  },
  userTimestamp: {
    marginTop: 4,
    marginRight: 4,
    fontSize: 10,
    color: "#94A3B8",
    fontWeight: "500",
  },

  // Inline Citation Pill
  citationPill: {
    fontSize: 12,
    fontWeight: "800",
    color: "#FFFFFF",
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 10,
    overflow: "hidden",
    marginHorizontal: 2,
  },

  // Horizontal Scrollable Source Cards
  sourceCardsContainer: {
    marginTop: 6,
    marginLeft: 52,
  },
  sourceCardsScroll: {
    paddingRight: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sourceCard: {
    width: 120,
    height: 80,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 8,
    padding: 8,
    justifyContent: "space-between",
  },
  sourceCardTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sourceCardIcon: {
    fontSize: 14,
  },
  sourceCardEid: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.4,
  },
  sourceCardName: {
    color: "#F8FAFC",
    fontSize: 11,
    fontWeight: "700",
    lineHeight: 14,
  },
  sourceCardMeta: {
    color: "#94A3B8",
    fontSize: 10,
    fontWeight: "500",
    lineHeight: 12,
  },
  moreSourcesCard: {
    width: 120,
    height: 80,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 8,
    padding: 8,
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  moreSourcesText: {
    color: "#0EA5E9",
    fontSize: 11,
    fontWeight: "800",
  },
  collapseSourcesButton: {
    height: 80,
    paddingHorizontal: 12,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
  },
  collapseSourcesText: {
    color: "#0EA5E9",
    fontSize: 11,
    fontWeight: "700",
  },

  // Thinking State
  thinkingContainer: {
    marginVertical: 8,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  thinkingCard: {
    flex: 1,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 16,
    overflow: "hidden",
  },
  thinkingCardBody: {
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  thinkingHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  thinkingTitle: {
    color: "#F8FAFC",
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 20,
  },
  bouncingDotsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    height: 14,
    justifyContent: "center",
  },
  bouncingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#0EA5E9",
  },
  thinkingSubtext: {
    marginTop: 6,
    color: "#94A3B8",
    fontSize: 12,
    lineHeight: 16,
    fontWeight: "400",
  },

  // Composer
  composerShell: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: Platform.OS === "ios" ? 14 : 12,
    borderTopWidth: 1,
    borderTopColor: "#1E293B",
    backgroundColor: "#0F172A",
  },
  sourceHint: {
    marginLeft: 8,
    marginBottom: 6,
    color: "#64748B",
    fontSize: 11,
    lineHeight: 15,
  },
  inputBar: {
    height: 56,
    backgroundColor: "#1E293B",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 28,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 6,
    gap: 6,
  },
  plusButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
    marginLeft: 4,
  },
  micButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#6366F1",
    alignItems: "center",
    justifyContent: "center",
  },
  input: {
    flex: 1,
    height: 48,
    paddingHorizontal: 8,
    color: "#F8FAFC",
    fontSize: 14,
    lineHeight: 18,
  },
  actionCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#0EA5E9",
    alignItems: "center",
    justifyContent: "center",
  },
  stopCircle: {
    backgroundColor: "#EF4444",
  },

  // Attachment Sheet
  sheetBackdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(15, 23, 42, 0.75)",
  },
  attachmentSheet: {
    backgroundColor: "#1E293B",
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    borderWidth: 1,
    borderColor: "#334155",
    paddingHorizontal: 20,
    paddingBottom: 36,
    paddingTop: 12,
  },
  sheetHandle: {
    alignSelf: "center",
    width: 38,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#475569",
    marginBottom: 16,
  },
  attachmentSheetTitle: {
    color: "#F8FAFC",
    fontSize: 18,
    fontWeight: "800",
  },
  attachmentSheetSubtitle: {
    marginTop: 3,
    color: "#94A3B8",
    fontSize: 12,
    marginBottom: 20,
  },
  attachmentGrid: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 10,
  },
  attachmentOption: {
    flex: 1,
    alignItems: "center",
    backgroundColor: "#0F172A",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 16,
    paddingVertical: 14,
    paddingHorizontal: 4,
  },
  attachmentIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  attachmentOptionTitle: {
    color: "#F8FAFC",
    fontSize: 12,
    fontWeight: "700",
  },
  attachmentOptionSub: {
    marginTop: 2,
    color: "#64748B",
    fontSize: 10,
  },
});
