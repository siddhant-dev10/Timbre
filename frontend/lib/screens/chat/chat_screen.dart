import 'dart:async';
import 'dart:convert';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../core/config/app_config.dart';
import '../../models/citizen.dart';
import '../../state/app_state.dart';

class ChatScreen extends StatefulWidget {
  final AppState state;

  const ChatScreen({super.key, required this.state});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _player = AudioPlayer();
  final List<_ChatMessage> _messages = [];
  String? _conversationId;
  Completer<void>? _abortRequest;
  bool _sending = false;
  bool _playing = false;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    final Citizen? citizen = widget.state.selectedCitizen;
    if (_sending || text.isEmpty) return;
    if (widget.state.isDemoMode || citizen == null) {
      _showMessage('Select backend mode and load a synthetic citizen first.');
      return;
    }

    setState(() {
      _sending = true;
      _messages.add(_ChatMessage(text, true));
      _controller.clear();
    });
    _scrollToEnd();

    try {
      final base = AppConfig.backendUrl.replaceFirst(RegExp(r'/+$'), '');
      final aborter = Completer<void>();
      _abortRequest = aborter;
      final request = http.AbortableRequest(
        'POST',
        Uri.parse('$base/chat'),
        abortTrigger: aborter.future,
      )
        ..headers['Content-Type'] = 'application/json'
        ..body = jsonEncode({
          'citizen_id': citizen.id,
          'message': text,
          'conversation_id': _conversationId,
          'language_preference': 'Hinglish',
        });
      final client = http.Client();
      late final http.Response response;
      try {
        final streamed = await client.send(request).timeout(AppConfig.requestTimeout * 9);
        response = await http.Response.fromStream(streamed).timeout(AppConfig.requestTimeout * 9);
      } finally {
        client.close();
      }
      final body = jsonDecode(response.body);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final detail = body is Map ? body['detail'] : null;
        throw Exception(detail is String ? detail : 'Request failed (${response.statusCode}).');
      }
      final data = body as Map<String, dynamic>;
      _conversationId = data['conversation_id'] as String?;
      if (!mounted) return;
      setState(() => _messages.add(_ChatMessage(data['answer'] as String, false)));
      _scrollToEnd();
    } on http.RequestAbortedException {
      if (mounted) {
        setState(() => _messages.add(const _ChatMessage(
          'Request cancelled. The backend or provider may still finish work already in progress.',
          false,
          isError: true,
        )));
      }
    } catch (error) {
      if (!mounted) return;
      final detail = error is Exception
          ? error.toString().replaceFirst('Exception: ', '')
          : 'Could not reach the local backend. Check that it is running.';
      setState(() => _messages.add(_ChatMessage('Message not delivered: $detail', false, isError: true)));
    } finally {
      _abortRequest = null;
      if (mounted) setState(() => _sending = false);
    }
  }

  void _cancelRequest() {
    final aborter = _abortRequest;
    if (aborter != null && !aborter.isCompleted) aborter.complete();
    if (_conversationId != null) {
      final base = AppConfig.backendUrl.replaceFirst(RegExp(r'/+$'), '');
      http.post(Uri.parse('$base/voice/playback/$_conversationId/cancel')).ignore();
    }
    if (_playing) {
      _player.stop();
      if (mounted) setState(() => _playing = false);
    }
  }

  Future<void> _speak(String text) async {
    if (_playing) {
      await _player.stop();
      if (mounted) setState(() => _playing = false);
      return;
    }
    setState(() => _playing = true);
    try {
      final base = AppConfig.backendUrl.replaceFirst(RegExp(r'/+$'), '');
      final response = await http
          .post(
            Uri.parse('$base/voice/synthesize'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text}),
          )
          .timeout(const Duration(seconds: 40));
      if (response.statusCode != 200) {
        final decoded = jsonDecode(response.body);
        final detail = decoded is Map ? decoded['detail'] : null;
        throw Exception(detail is String ? detail : 'Speech synthesis failed (${response.statusCode}).');
      }
      await _player.play(BytesSource(response.bodyBytes));
      await _player.onPlayerComplete.first;
    } catch (error) {
      if (!mounted) return;
      final detail = error is Exception
          ? error.toString().replaceFirst('Exception: ', '')
          : 'Audio playback failed.';
      _showMessage(detail);
    } finally {
      if (mounted) setState(() => _playing = false);
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final citizen = state.selectedCitizen;
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Conversation', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text(
            state.isDemoMode
                ? 'Text chat is available in backend mode. Demo mode makes no provider calls.'
                : 'Using synthetic profile: ${citizen?.fullName ?? 'none selected'}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          Expanded(
            child: Card(
              child: _messages.isEmpty
                  ? const Center(child: Text('Ask about a government service. Responses are preliminary guidance.'))
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(20),
                      itemCount: _messages.length + (_sending ? 1 : 0),
                      itemBuilder: (context, index) {
                        if (index == _messages.length) {
                          return const Padding(
                            padding: EdgeInsets.all(12),
                            child: Row(children: [SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)), SizedBox(width: 10), Text('Timbre is responding…')]),
                          );
                        }
                        final message = _messages[index];
                        return Align(
                          alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
                          child: Container(
                            constraints: const BoxConstraints(maxWidth: 640),
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            decoration: BoxDecoration(
                              color: message.isError
                                  ? Theme.of(context).colorScheme.errorContainer
                                  : message.isUser
                                      ? Theme.of(context).colorScheme.primaryContainer
                                      : Theme.of(context).colorScheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(message.text),
                                if (!message.isUser && !message.isError)
                                  Align(
                                    alignment: Alignment.centerRight,
                                    child: IconButton(
                                      tooltip: _playing ? 'Stop audio' : 'Speak response with ElevenLabs',
                                      onPressed: () => _speak(message.text),
                                      icon: Icon(_playing ? Icons.stop_circle_outlined : Icons.volume_up_outlined),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  enabled: !_sending,
                  maxLength: 4000,
                  minLines: 1,
                  maxLines: 4,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(
                    hintText: 'Type in Hindi, Hinglish, or English…',
                    counterText: '',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                tooltip: _sending ? 'Cancel waiting for response' : 'Send message',
                onPressed: _sending ? _cancelRequest : _send,
                icon: Icon(_sending ? Icons.stop : Icons.send),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ChatMessage {
  final String text;
  final bool isUser;
  final bool isError;

  const _ChatMessage(this.text, this.isUser, {this.isError = false});
}
